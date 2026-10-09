from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import Field, StringConstraints
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import Identidad, identidad_actual, usuario_registrado
from app.config import get_settings
from app.db import get_db
from app.dominio.notificaciones import TipoNotificacion, mensaje_nuevo_registro
from app.dominio.registro import es_codigo_de_coordinacion
from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, RolUsuario, Usuario
from app.reloj import Reloj, get_reloj, hoy
from app.repos.usuarios import buscar_por_email
from app.servicios.notificaciones import destinatarios, notificar

router = APIRouter()


class UsuarioOut(Esquema):
    id: int
    nombre: str
    email: str
    rol: RolUsuario
    estado: EstadoUsuario


def _a_salida(usuario: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=usuario.id, nombre=usuario.nombre, email=usuario.email, rol=usuario.rol, estado=usuario.estado
    )


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(usuario_registrado)) -> UsuarioOut:
    """Usuario de la sesión, en cualquier estado: la interfaz muestra "esperando activación" si está PENDIENTE."""
    return _a_salida(usuario)


# Restricción violada -> (código, mensaje) del 409. Regla 8: la carrera entre dos registros la resuelve la base.
_CONFLICTOS_DE_REGISTRO = {
    "usuario_auth_id_key": ("YA_REGISTRADO", "Esta cuenta ya está registrada."),
    "ux_usuario_email_lower": ("EMAIL_YA_REGISTRADO", "Ese email ya está registrado con otra cuenta."),
}


class RegistroIn(Esquema):
    nombre: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    codigo_coordinacion: str | None = Field(default=None, max_length=64)


@router.post("/registro", response_model=UsuarioOut, status_code=201)
def registrar(
    datos: RegistroIn,
    respuesta: Response,
    identidad: Identidad = Depends(identidad_actual),
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
) -> UsuarioOut:
    """Completa el registro de una cuenta ya creada en Supabase Auth (D30).

    Con el código de coordinación correcto queda COORDINADOR ACTIVO; sin código, MEDICO PENDIENTE hasta
    que un coordinador lo active. Si el email ya estaba cargado sin cuenta (datos de ejemplo, D28),
    vincula la cuenta, conserva nombre, rol y estado, y responde 200. Vincular un coordinador cargado exige
    el código: sin confirmación de email (D06), cualquiera podría crear la cuenta con ese email.
    Si la cuenta queda PENDIENTE, avisa a los coordinadores activos en la misma transacción (D22).
    """
    if identidad.email is None:
        raise ErrorDominio("TOKEN_SIN_EMAIL", "El token de sesión no trae el email de la cuenta.", 403)
    codigo = (datos.codigo_coordinacion or "").strip()
    if codigo and not es_codigo_de_coordinacion(codigo, get_settings().codigo_coordinacion):
        raise ErrorDominio("CODIGO_INVALIDO", "El código de coordinación no es correcto.", 422)

    existente = buscar_por_email(db, identidad.email)
    if existente is not None and existente.auth_id == identidad.auth_id:
        raise ErrorDominio("YA_REGISTRADO", "Esta cuenta ya está registrada.", 409)
    if existente is not None and existente.auth_id is not None:
        raise ErrorDominio("EMAIL_YA_REGISTRADO", "Ese email ya está registrado con otra cuenta.", 409)

    if existente is not None and existente.rol == RolUsuario.COORDINADOR and not codigo:
        # Sin confirmación de email (D06), cualquiera puede crear en Supabase la cuenta de un email cargado:
        # tomar la de un coordinador exige el mismo código que registrarse como coordinador (D30).
        raise ErrorDominio("CODIGO_REQUERIDO", "Para vincular una cuenta de coordinador hace falta el código.", 422)
    if existente is not None:
        # Regla 8: el UPDATE solo vincula si la fila sigue sin cuenta; si otro registro la vinculó entre
        # la búsqueda y acá, no la pisa.
        vinculada = db.execute(
            update(Usuario)
            .where(Usuario.id == existente.id, Usuario.auth_id.is_(None))
            .values(auth_id=identidad.auth_id)
            .execution_options(synchronize_session=False)
        )
        if vinculada.rowcount == 0:
            raise ErrorDominio("EMAIL_YA_REGISTRADO", "Ese email ya está registrado con otra cuenta.", 409)
        db.refresh(existente)
        usuario = existente
        respuesta.status_code = 200
    else:
        coordinador = bool(codigo)
        usuario = Usuario(
            nombre=datos.nombre,
            email=identidad.email,
            rol=RolUsuario.COORDINADOR if coordinador else RolUsuario.MEDICO,
            estado=EstadoUsuario.ACTIVO if coordinador else EstadoUsuario.PENDIENTE,
            auth_id=identidad.auth_id,
        )
        db.add(usuario)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        restriccion = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if restriccion not in _CONFLICTOS_DE_REGISTRO:
            raise
        codigo_error, mensaje = _CONFLICTOS_DE_REGISTRO[restriccion]
        raise ErrorDominio(codigo_error, mensaje, 409) from exc
    if usuario.estado == EstadoUsuario.PENDIENTE:
        notificar(
            db,
            destinatarios(db, RolUsuario.COORDINADOR, hoy(reloj)),
            TipoNotificacion.NUEVO_REGISTRO,
            mensaje_nuevo_registro(usuario.nombre),
            reloj.ahora(),
            datos={"usuario_id": usuario.id},
        )
    db.commit()
    return _a_salida(usuario)

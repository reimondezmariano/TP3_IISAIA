"""Operaciones de staff sobre usuarios (D23, D24, D26, D30). No hacen commit; nunca borran un usuario."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, RolUsuario, Usuario
from app.repos.horarios import TurnoAfectado
from app.repos.usuarios import bloquear_con_coordinadores, bloquear_usuario
from app.servicios.plantilla import dejar_sin_titular


@dataclass(frozen=True)
class ResultadoCambio:
    usuario: Usuario
    horarios_sin_titular: list[int] = field(default_factory=list)
    turnos_afectados: list[TurnoAfectado] = field(default_factory=list)


def _bloquear(sesion: Session, usuario_id: int) -> Usuario:
    usuario = bloquear_usuario(sesion, usuario_id)
    if usuario is None:
        raise ErrorDominio("USUARIO_NO_ENCONTRADO", "No existe ese usuario.", 404)
    if usuario.estado == EstadoUsuario.BAJA:
        raise ErrorDominio("USUARIO_DADO_DE_BAJA", "El usuario está dado de baja.", 409)
    return usuario


def activar(sesion: Session, usuario_id: int) -> ResultadoCambio:
    """Un médico que se registró sin código queda PENDIENTE hasta que un coordinador lo activa (D30)."""
    usuario = _bloquear(sesion, usuario_id)
    if usuario.estado != EstadoUsuario.PENDIENTE:
        raise ErrorDominio("YA_ACTIVO", "El usuario ya está activo.", 409)
    usuario.estado = EstadoUsuario.ACTIVO
    sesion.flush()
    return ResultadoCambio(usuario)


def dar_de_baja(sesion: Session, usuario_id: int, fecha_baja: date, hoy: date) -> ResultadoCambio:
    """Baja definitiva de un médico (D24). `fecha_baja` es su último día activo (decisión 1 del plan de F5).

    Sus horarios quedan sin titular desde el día siguiente. El estado pasa a BAJA ya, pero la cuenta
    entra hasta `fecha_baja` inclusive (app/auth.py). Nunca se borra el usuario.
    """
    usuario = _bloquear(sesion, usuario_id)
    if usuario.rol != RolUsuario.MEDICO:
        raise ErrorDominio("BAJA_SOLO_MEDICOS", "Solo se da de baja a un médico; un coordinador pasa antes a médico.")
    if fecha_baja < hoy:
        raise ErrorDominio("FECHA_PASADA", f"La fecha de baja no puede ser anterior a hoy ({hoy:%d/%m/%Y}).")
    horarios, afectados = dejar_sin_titular(sesion, usuario.id, fecha_baja + timedelta(days=1), hoy)
    usuario.estado = EstadoUsuario.BAJA
    usuario.fecha_baja = fecha_baja
    sesion.flush()
    return ResultadoCambio(usuario, horarios, afectados)


def cambiar_rol(
    sesion: Session, usuario_id: int, rol: RolUsuario, hoy: date, activar_antes: bool = False
) -> ResultadoCambio:
    """Roles excluyentes (D23). Siempre queda al menos un coordinador activo.

    Un médico que pasa a coordinador deja sus horarios sin titular desde mañana, en la misma transacción:
    hoy todavía hace su guardia (decisión 4 del plan de F5). Con `activar_antes`, activa al usuario pendiente
    sobre la fila ya bloqueada junto con los coordinadores: llamar antes a `activar` lo bloquearía fuera del
    orden por id y podría cerrar un ciclo con otro cambio de rol.
    """
    usuario, coordinadores = bloquear_con_coordinadores(sesion, usuario_id)
    if usuario is None:
        raise ErrorDominio("USUARIO_NO_ENCONTRADO", "No existe ese usuario.", 404)
    if usuario.estado == EstadoUsuario.BAJA:
        raise ErrorDominio("USUARIO_DADO_DE_BAJA", "El usuario está dado de baja.", 409)
    if activar_antes:
        if usuario.estado != EstadoUsuario.PENDIENTE:
            raise ErrorDominio("YA_ACTIVO", "El usuario ya está activo.", 409)
        usuario.estado = EstadoUsuario.ACTIVO
    if usuario.rol == rol:
        raise ErrorDominio("SIN_CAMBIOS", "El usuario ya tiene ese rol.")
    if rol == RolUsuario.MEDICO:
        if not any(c.id != usuario.id for c in coordinadores):
            raise ErrorDominio("ULTIMO_COORDINADOR", "Tiene que quedar al menos un coordinador activo (D23).")
        usuario.rol = RolUsuario.MEDICO
        sesion.flush()
        return ResultadoCambio(usuario)
    horarios, afectados = dejar_sin_titular(sesion, usuario.id, hoy + timedelta(days=1), hoy)
    usuario.rol = RolUsuario.COORDINADOR
    sesion.flush()
    return ResultadoCambio(usuario, horarios, afectados)

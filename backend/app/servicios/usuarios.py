"""Operaciones de staff sobre usuarios (D23, D24, D26, D30). No hacen commit; nunca borran un usuario."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, RolUsuario, Usuario
from app.repos.horarios import TurnoAfectado
from app.repos.usuarios import bloquear_usuario
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

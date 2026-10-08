"""Operaciones de staff sobre usuarios (D23, D24, D26, D30). No hacen commit; nunca borran un usuario."""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, Usuario
from app.repos.horarios import TurnoAfectado
from app.repos.usuarios import bloquear_usuario


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

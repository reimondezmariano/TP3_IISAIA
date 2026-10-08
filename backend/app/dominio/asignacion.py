"""Quién puede cubrir un turno y qué tipo de asignación es (D16, D18, D23, D24). Lógica pura: sin base ni FastAPI."""

from datetime import date
from enum import Enum

from app.modelos import EstadoUsuario, RolUsuario


class CasoAsignacion(str, Enum):
    """Los tres casos que distingue el único endpoint de asignación (D18)."""

    CANDIDATO_ELEGIDO = "CANDIDATO_ELEGIDO"
    ASIGNACION_DIRECTA = "ASIGNACION_DIRECTA"
    REASIGNACION = "REASIGNACION"


def habilitado_para_turno(rol: RolUsuario, estado: EstadoUsuario, fecha_baja: date | None, fecha_turno: date) -> bool:
    """Puede postularse y ser asignado a un turno que empieza en `fecha_turno`.

    Solo los médicos (D23). Un pendiente no tiene acceso; un dado de baja cubre turnos hasta su
    `fecha_baja` inclusive y no después (D24).
    """
    if rol != RolUsuario.MEDICO:
        return False
    if estado == EstadoUsuario.ACTIVO:
        return True
    if estado == EstadoUsuario.BAJA:
        return fecha_baja is not None and fecha_turno <= fecha_baja
    return False


def clasificar_asignacion(tiene_asignado: bool, es_candidato: bool) -> CasoAsignacion:
    """Reasignación si el turno ya tenía asignado; si no, elección de un candidato o asignación directa (D18)."""
    if tiene_asignado:
        return CasoAsignacion.REASIGNACION
    return CasoAsignacion.CANDIDATO_ELEGIDO if es_candidato else CasoAsignacion.ASIGNACION_DIRECTA

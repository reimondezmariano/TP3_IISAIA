"""Consolidación perezosa e idempotente de turnos terminados (D20). Lógica pura: sin base de datos ni FastAPI."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from app.dominio.tiempo import exigir_zona


@dataclass(frozen=True)
class TurnoConsolidable:
    turno_id: str  # id compuesto "horarioId:fecha" (D09): el turno puede no tener fila todavía (D11)
    fin: datetime
    titular_id: int | None
    asignado_id: int | None
    hay_vacante_abierta: bool
    sin_cobertura: bool
    consolidado_en: datetime | None


@dataclass(frozen=True)
class Consolidacion:
    turno_id: str
    realizador_id: int | None
    consolidado_en: datetime


def realizador_presunto(
    titular_id: int | None,
    asignado_id: int | None,
    hay_vacante_abierta: bool,
    sin_cobertura: bool,
) -> int | None:
    """Quién se presume que hizo la guardia (D20); None si se consolida sin realizador (D19).

    Con una vacante abierta no hay realizador presunto, aunque quede un asignado o un titular (defensa de D31).
    Sin vacante abierta: el asignado vigente y, si no hay, el titular.
    """
    if hay_vacante_abierta or sin_cobertura:
        return None
    if asignado_id is not None:
        return asignado_id
    return titular_id


def consolidar(turnos: Iterable[TurnoConsolidable], ahora: datetime) -> list[Consolidacion]:
    """Consolidaciones por aplicar: turnos terminados que todavía no se consolidaron. Idempotente (D20)."""
    exigir_zona(ahora)
    resultado: list[Consolidacion] = []
    for turno in turnos:
        exigir_zona(turno.fin)
        if turno.consolidado_en is not None or turno.fin > ahora:
            continue
        realizador = realizador_presunto(
            turno.titular_id, turno.asignado_id, turno.hay_vacante_abierta, turno.sin_cobertura
        )
        resultado.append(Consolidacion(turno.turno_id, realizador, ahora))
    return resultado

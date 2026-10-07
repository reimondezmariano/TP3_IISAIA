"""Elegibilidad de postulantes a un turno (D16). Lógica pura: sin base de datos ni FastAPI."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.dominio.tiempo import exigir_zona


class Motivo(Enum):
    ES_TITULAR = "ES_TITULAR"
    GUARDIA_SUPERPUESTA = "GUARDIA_SUPERPUESTA"


@dataclass(frozen=True)
class Guardia:
    inicio: datetime
    fin: datetime


def motivo_inelegibilidad(
    medico_id: int,
    titular_id: int | None,
    inicio: datetime,
    fin: datetime,
    guardias_del_medico: Iterable[Guardia],
) -> Motivo | None:
    """Por qué el médico no puede postularse al turno [inicio, fin), o None si es elegible (D16).

    `guardias_del_medico` son sus guardias vigentes, sin incluir el turno evaluado. Se recalcula en cada
    consulta: si el impedimento desaparece, el médico vuelve a ser elegible.
    """
    guardias = list(guardias_del_medico)
    exigir_zona(inicio, fin, *(instante for g in guardias for instante in (g.inicio, g.fin)))
    if medico_id == titular_id:
        return Motivo.ES_TITULAR
    if any(g.inicio < fin and g.fin > inicio for g in guardias):
        return Motivo.GUARDIA_SUPERPUESTA
    return None


def es_elegible(
    medico_id: int,
    titular_id: int | None,
    inicio: datetime,
    fin: datetime,
    guardias_del_medico: Iterable[Guardia],
) -> bool:
    return motivo_inelegibilidad(medico_id, titular_id, inicio, fin, guardias_del_medico) is None

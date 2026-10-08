"""Alertas escalonadas de turno sin cobertura (D19). Lógica pura: sin base de datos ni FastAPI."""

from collections.abc import Collection
from datetime import datetime, timedelta
from enum import Enum

from app.dominio.tiempo import exigir_zona


class Umbral(Enum):
    HORAS_48 = "48H"
    HORAS_24 = "24H"
    INICIO = "INICIO"


# Anticipación al inicio con que vence cada umbral, en orden cronológico (D19).
_ANTICIPACION = {
    Umbral.HORAS_48: timedelta(hours=48),
    Umbral.HORAS_24: timedelta(hours=24),
    Umbral.INICIO: timedelta(0),
}


def alertas_pendientes(
    inicio: datetime,
    fin: datetime,
    vacante_abierta_desde: datetime,
    ahora: datetime,
    enviadas: Collection[Umbral],
) -> list[Umbral]:
    """Umbrales por avisar a los coordinadores, una sola vez por turno y umbral (D19).

    Un umbral solo cuenta si su instante cae mientras la vacante estaba abierta y el turno no terminó.
    """
    exigir_zona(inicio, fin, vacante_abierta_desde, ahora)
    if ahora >= fin:
        return []
    return [
        umbral
        for umbral, anticipacion in _ANTICIPACION.items()
        if umbral not in enviadas and vacante_abierta_desde <= inicio - anticipacion <= ahora
    ]

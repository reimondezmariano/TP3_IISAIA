"""Reglas de vacantes (D15). Lógica pura: sin base de datos ni FastAPI."""

from datetime import datetime, timedelta

from app.dominio.tiempo import exigir_zona

# D15: una vacante generada con menos de 24 h de anticipación es urgente.
ANTICIPACION_URGENTE = timedelta(hours=24)


def es_urgente(inicio_turno: datetime, generada_en: datetime) -> bool:
    exigir_zona(inicio_turno, generada_en)
    return inicio_turno - generada_en < ANTICIPACION_URGENTE

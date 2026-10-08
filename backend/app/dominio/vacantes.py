"""Reglas de vacantes (D15). Lógica pura: sin base de datos ni FastAPI."""

from datetime import datetime, timedelta

from app.dominio.tiempo import exigir_zona

# D15: una vacante generada con menos de 24 h de anticipación es urgente.
ANTICIPACION_URGENTE = timedelta(hours=24)


def es_urgente(inicio_turno: datetime, generada_en: datetime) -> bool:
    exigir_zona(inicio_turno, generada_en)
    return inicio_turno - generada_en < ANTICIPACION_URGENTE


def puede_generar(actor_id: int, es_coordinador: bool, titular_id: int | None, asignado_id: int | None) -> bool:
    """Generan la vacante el titular, el asignado vigente o un coordinador (D15)."""
    return es_coordinador or actor_id in (titular_id, asignado_id)


def puede_retirar(actor_id: int, es_coordinador: bool, generada_por_id: int) -> bool:
    """Retiran la vacante quien la generó o un coordinador (D15)."""
    return es_coordinador or actor_id == generada_por_id


def asignado_a_restaurar(generada_por_id: int, asignado_anterior_id: int | None) -> int | None:
    """Al retirar una vacante se restaura al asignado que había (D31) solo si fue quien la generó."""
    return asignado_anterior_id if asignado_anterior_id == generada_por_id else None

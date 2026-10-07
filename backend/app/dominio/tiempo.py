"""Utilidades de tiempo para las reglas de dominio. Lógica pura: no consulta la hora del sistema (D27)."""

from datetime import datetime


def exigir_zona(*instantes: datetime) -> None:
    """Todo instante del dominio lleva zona horaria; uno sin zona es un error de programación."""
    for instante in instantes:
        if instante.tzinfo is None or instante.utcoffset() is None:
            raise ValueError(f"El instante {instante.isoformat()} no tiene zona horaria")

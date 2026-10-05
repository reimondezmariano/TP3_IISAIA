"""Reloj inyectable (D27). Es el único módulo que consulta la hora del sistema."""

from datetime import datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from app.config import get_settings


class Reloj(Protocol):
    def ahora(self) -> datetime: ...


class RelojSistema:
    def __init__(self, zona: ZoneInfo) -> None:
        self._zona = zona

    def ahora(self) -> datetime:
        return datetime.now(self._zona)


class RelojFijo:
    """Reloj para pruebas: siempre devuelve el mismo instante hasta que se lo avanza."""

    def __init__(self, instante: datetime) -> None:
        if instante.tzinfo is None:
            raise ValueError("RelojFijo necesita un instante con zona horaria")
        self._instante = instante

    def ahora(self) -> datetime:
        return self._instante

    def avanzar(self, delta: timedelta) -> None:
        self._instante = self._instante + delta


def get_reloj() -> Reloj:
    return RelojSistema(get_settings().zona)

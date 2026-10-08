"""Reloj inyectable (D27). Es el único módulo que consulta la hora del sistema."""

from datetime import date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.repos.consolidacion import desfase_demo


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


class RelojDesplazado:
    """Reloj del modo demo (D27): la hora de otro reloj más un desfase que fija POST /demo/reloj."""

    def __init__(self, base: Reloj, desfase: timedelta) -> None:
        self._base = base
        self._desfase = desfase

    def ahora(self) -> datetime:
        return self._base.ahora() + self._desfase


def get_reloj_sistema() -> Reloj:
    """Hora real, sin desfase. Solo la usa POST /demo/reloj para calcular el desfase."""
    return RelojSistema(get_settings().zona)


def get_reloj(db: Session = Depends(get_db)) -> Reloj:
    """Hora real; en modo demo, más el desfase guardado por POST /demo/reloj (D27)."""
    settings = get_settings()
    sistema = RelojSistema(settings.zona)
    if settings.modo_demo:
        return RelojDesplazado(sistema, desfase_demo(db))
    return sistema


def hoy(reloj: Reloj) -> date:
    """Fecha de "ahora" en la zona del servicio (D13). Toda regla que compare con hoy usa esta función."""
    return reloj.ahora().astimezone(get_settings().zona).date()

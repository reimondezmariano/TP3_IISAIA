"""Reloj inyectable (D27). Es el único módulo que consulta la hora del sistema."""

from datetime import date, datetime, timedelta
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


class RelojDesplazado:
    """Reloj del modo demo (D27): la hora de otro reloj más un desfase que fija POST /demo/reloj."""

    def __init__(self, base: Reloj, desfase: timedelta) -> None:
        self._base = base
        self._desfase = desfase

    def ahora(self) -> datetime:
        return self._base.ahora() + self._desfase


# D27: desfase del reloj de demo. Vive en memoria: la demo corre en un solo proceso y reiniciarlo vuelve a la
# hora real. Fuera del modo demo no se usa.
_desfase_demo = timedelta(0)


def desfase_demo() -> timedelta:
    return _desfase_demo


def fijar_desfase_demo(desfase: timedelta) -> None:
    global _desfase_demo
    _desfase_demo = desfase


def get_reloj_sistema() -> Reloj:
    """Hora real, sin desfase. Solo la usa POST /demo/reloj para calcular el desfase."""
    return RelojSistema(get_settings().zona)


def get_reloj() -> Reloj:
    settings = get_settings()
    sistema = RelojSistema(settings.zona)
    if settings.modo_demo:
        return RelojDesplazado(sistema, _desfase_demo)
    return sistema


def hoy(reloj: Reloj) -> date:
    """Fecha de "ahora" en la zona del servicio (D13). Toda regla que compare con hoy usa esta función."""
    return reloj.ahora().astimezone(get_settings().zona).date()

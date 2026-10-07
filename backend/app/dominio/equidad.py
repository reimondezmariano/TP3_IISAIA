"""Orden de candidatos por equidad (D17). Lógica pura: sin base de datos ni FastAPI."""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.dominio.elegibilidad import Guardia
from app.dominio.tiempo import exigir_zona


@dataclass(frozen=True)
class Candidato:
    medico_id: int
    postulado_en: datetime


@dataclass(frozen=True)
class TurnoDelMes:
    inicio: datetime
    asignado_id: int | None
    titular_id: int | None


def contar_coberturas(turnos: Iterable[TurnoDelMes], anio: int, mes: int, zona: ZoneInfo) -> dict[int, int]:
    """Coberturas por médico en el mes calendario (en `zona`): turnos asignados a alguien que no es su titular."""
    cuenta: Counter[int] = Counter()
    for turno in turnos:
        exigir_zona(turno.inicio)
        inicio = turno.inicio.astimezone(zona)
        if (inicio.year, inicio.month) != (anio, mes):
            continue
        if turno.asignado_id is not None and turno.asignado_id != turno.titular_id:
            cuenta[turno.asignado_id] += 1
    return dict(cuenta)


def ordenar_candidatos(candidatos: Iterable[Candidato], coberturas: Mapping[int, int]) -> list[Candidato]:
    """Primero quien cubrió menos; desempata la hora de postulación y, en último caso, el id del médico."""
    lista = list(candidatos)
    exigir_zona(*(c.postulado_en for c in lista))
    return sorted(lista, key=lambda c: (coberturas.get(c.medico_id, 0), c.postulado_en, c.medico_id))


def horas_en_semana(guardias: Iterable[Guardia], dia_referencia: date, zona: ZoneInfo) -> float:
    """Horas de guardia dentro de la semana (lunes a lunes, en `zona`) de `dia_referencia`.

    Dato informativo de D17: no interviene en el orden. Lo que cruza el borde de la semana se prorratea.
    """
    lunes = dia_referencia - timedelta(days=dia_referencia.weekday())
    inicio_semana = datetime.combine(lunes, time(0), tzinfo=zona)
    fin_semana = datetime.combine(lunes + timedelta(days=7), time(0), tzinfo=zona)
    total = timedelta(0)
    for guardia in guardias:
        exigir_zona(guardia.inicio, guardia.fin)
        desde = max(guardia.inicio, inicio_semana)
        hasta = min(guardia.fin, fin_semana)
        if hasta > desde:
            total += hasta - desde
    return total / timedelta(hours=1)

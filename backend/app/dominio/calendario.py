"""Cálculo de turnos desde la plantilla (D11, D13, D14). Lógica pura: sin base de datos ni FastAPI."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.errores import ErrorDominio


@dataclass(frozen=True)
class Titular:
    id: int
    nombre: str


@dataclass(frozen=True)
class VersionPlantilla:
    version_id: int
    horario_id: int
    titular: Titular | None
    dia_semana: int
    hora_inicio: time
    duracion_horas: int
    frecuencia_semanas: int
    fecha_ancla: date
    vigente_desde: date
    vigente_hasta: date | None


@dataclass(frozen=True)
class TurnoCalculado:
    id: str
    horario_id: int
    fecha: date
    inicio: datetime
    fin: datetime
    duracion_horas: int
    version_id: int
    titular: Titular | None


def formatear_id_turno(horario_id: int, fecha: date) -> str:
    return f"{horario_id}:{fecha.isoformat()}"


_PATRON_ID = re.compile(r"(\d+):(\d{4}-\d{2}-\d{2})", re.ASCII)


def parsear_id_turno(texto: str) -> tuple[int, date]:
    coincidencia = _PATRON_ID.fullmatch(texto)
    if coincidencia is None:
        raise ErrorDominio("TURNO_ID_INVALIDO", f"Identificador de turno inválido: {texto!r}.")
    try:
        fecha = date.fromisoformat(coincidencia.group(2))
    except ValueError as exc:
        raise ErrorDominio("TURNO_ID_INVALIDO", f"Identificador de turno inválido: {texto!r}.") from exc
    return int(coincidencia.group(1)), fecha


def _lunes(fecha: date) -> date:
    return fecha - timedelta(days=fecha.weekday())


def _se_cumple(version: VersionPlantilla, fecha: date) -> bool:
    if fecha.isoweekday() != version.dia_semana:
        return False
    # La vigencia se evalúa sobre la fecha de inicio: el turno pertenece al día en que empieza (D13).
    if fecha < version.vigente_desde:
        return False
    if version.vigente_hasta is not None and fecha >= version.vigente_hasta:
        return False
    semanas = (_lunes(fecha) - version.fecha_ancla).days // 7
    return semanas % version.frecuencia_semanas == 0


def calcular_turnos(
    versiones: Sequence[VersionPlantilla], desde: date, hasta: date, zona: ZoneInfo
) -> list[TurnoCalculado]:
    """Turnos cuyo intervalo se superpone con [desde 00:00, hasta + 1 día 00:00) en la zona del servicio."""
    inicio_ventana = datetime.combine(desde, time(0), tzinfo=zona)
    fin_ventana = datetime.combine(hasta + timedelta(days=1), time(0), tzinfo=zona)

    resultado: list[TurnoCalculado] = []
    # Con duración máxima de 24 h, solo un turno del día anterior puede entrar en la ventana.
    fecha = desde - timedelta(days=1)
    while fecha <= hasta:
        for version in versiones:
            if not _se_cumple(version, fecha):
                continue
            inicio = datetime.combine(fecha, version.hora_inicio, tzinfo=zona)
            fin = (inicio.astimezone(UTC) + timedelta(hours=version.duracion_horas)).astimezone(zona)
            if inicio < fin_ventana and fin > inicio_ventana:
                resultado.append(
                    TurnoCalculado(
                        id=formatear_id_turno(version.horario_id, fecha),
                        horario_id=version.horario_id,
                        fecha=fecha,
                        inicio=inicio,
                        fin=fin,
                        duracion_horas=version.duracion_horas,
                        version_id=version.version_id,
                        titular=version.titular,
                    )
                )
        fecha += timedelta(days=1)

    resultado.sort(key=lambda turno: (turno.inicio, turno.horario_id))
    return resultado

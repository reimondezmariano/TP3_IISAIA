"""Consolidación perezosa e idempotente (D20): corre antes de responder, sin proceso programado. No hace commit."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.dominio.calendario import TurnoCalculado, calcular_turnos, formatear_id_turno
from app.dominio.consolidacion import Consolidacion, TurnoConsolidable, consolidar
from app.modelos import EstadoVacante, EventoTurno, TipoEventoTurno
from app.reloj import Reloj, hoy
from app.repos.consolidacion import (
    bloquear_marca,
    fechas_de_baja,
    guardar_marca,
    insertar_consolidados,
    primera_vigencia,
    turnos_guardados_por_consolidar,
)
from app.repos.horarios import versiones_en_rango
from app.servicios.alertas import emitir_alertas


@dataclass(frozen=True)
class ResultadoConsolidacion:
    consolidados: int
    vacantes_sin_cobertura: int


def consolidar_pendientes(sesion: Session, reloj: Reloj, zona: ZoneInfo) -> ResultadoConsolidacion:
    ahora = reloj.ahora()
    marca = bloquear_marca(sesion)
    calculados = _consolidar_calculados(sesion, marca, hoy(reloj), ahora, zona)
    guardados, cerradas = _consolidar_guardados(sesion, ahora)
    return ResultadoConsolidacion(calculados + guardados, cerradas)


def _consolidar_calculados(sesion: Session, marca: date | None, dia: date, ahora: datetime, zona: ZoneInfo) -> int:
    """Turnos que nunca se guardaron: se calculan desde la plantilla y se guardan ya consolidados (D11)."""
    desde = marca if marca is not None else primera_vigencia(sesion)
    if desde is None or desde > dia:
        return 0
    turnos = [t for t in calcular_turnos(versiones_en_rango(sesion, desde, dia), desde, dia, zona) if t.fecha >= desde]
    por_id = {t.id: t for t in turnos}
    pendientes = [
        TurnoConsolidable(t.id, t.fin, t.titular.id if t.titular else None, None, False, False, None) for t in turnos
    ]
    filas = [_fila(por_id[c.turno_id], c) for c in consolidar(pendientes, ahora)]
    insertados = insertar_consolidados(sesion, filas)
    # La próxima vez se parte del primer turno que todavía no terminó (o de hoy): nunca se retrocede.
    sin_terminar = [t.fecha for t in turnos if t.fin > ahora]
    guardar_marca(sesion, max(desde, min(sin_terminar, default=dia)))
    return insertados


def _fila(turno: TurnoCalculado, consolidacion: Consolidacion) -> dict[str, Any]:
    """Fila del turno con la foto de su versión (D11), ya consolidada."""
    return {
        "horario_id": turno.horario_id,
        "fecha": turno.fecha,
        "version_id": turno.version_id,
        "inicio": turno.inicio,
        "fin": turno.fin,
        "titular_id": turno.titular.id if turno.titular else None,
        "realizador_id": consolidacion.realizador_id,
        "consolidado_en": consolidacion.consolidado_en,
    }


def _consolidar_guardados(sesion: Session, ahora: datetime) -> tuple[int, int]:
    """Turnos con fila: se usa su foto (D11, D12). Una vacante abierta al terminar queda SIN_COBERTURA (D19, D31)."""
    pendientes = turnos_guardados_por_consolidar(sesion, ahora)
    por_id = {formatear_id_turno(t.horario_id, t.fecha): (t, v) for t, v in pendientes}
    consolidables = [
        TurnoConsolidable(
            turno_id,
            turno.fin,
            turno.titular_id,
            turno.asignado_id,
            vacante is not None,
            turno.sin_cobertura_en is not None,
            turno.consolidado_en,
        )
        for turno_id, (turno, vacante) in por_id.items()
    ]
    consolidaciones = consolidar(consolidables, ahora)
    bajas = fechas_de_baja(sesion, {c.realizador_id for c in consolidaciones if c.realizador_id is not None})
    cerradas = 0
    for consolidacion in consolidaciones:
        turno, vacante = por_id[consolidacion.turno_id]
        if vacante is not None:
            vacante.estado = EstadoVacante.SIN_COBERTURA
            vacante.cerrada_en = ahora
            if turno.sin_cobertura_en is None:
                turno.sin_cobertura_en = ahora
            sesion.add(
                EventoTurno(
                    turno_id=turno.id,
                    tipo=TipoEventoTurno.TURNO_SIN_COBERTURA,
                    actor_id=None,
                    ocurrido_en=ahora,
                    datos={"vacante_id": vacante.id, "al_consolidar": True},
                )
            )
            cerradas += 1
        realizador = consolidacion.realizador_id
        # D24: la foto puede nombrar a alguien que se dio de baja antes del turno; no lo hizo él.
        if realizador in bajas and bajas[realizador] < turno.fecha:
            realizador = None
        turno.realizador_id = realizador
        turno.consolidado_en = consolidacion.consolidado_en
    sesion.flush()
    return len(por_id), cerradas


@dataclass(frozen=True)
class ResultadoPuestaAlDia:
    consolidados: int
    vacantes_sin_cobertura: int
    alertas: int


def ponerse_al_dia(sesion: Session, reloj: Reloj, zona: ZoneInfo) -> ResultadoPuestaAlDia:
    """Lo que antes haría un proceso programado (D19, D20): consolidar y después avisar. No hace commit."""
    consolidacion = consolidar_pendientes(sesion, reloj, zona)
    alertas = emitir_alertas(sesion, reloj, zona)
    return ResultadoPuestaAlDia(consolidacion.consolidados, consolidacion.vacantes_sin_cobertura, alertas)

"""Turnos guardados (D09, D11). No hacen commit; trabajan dentro de la transacción de quien llama."""

from collections.abc import Iterable
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.dominio.calendario import calcular_turnos, parsear_id_turno
from app.errores import ErrorDominio
from app.modelos import Turno
from app.repos.horarios import versiones_en_rango


def _no_existe(turno_id: str) -> ErrorDominio:
    return ErrorDominio("TURNO_NO_ENCONTRADO", f"No existe el turno {turno_id}.", 404)


def _buscar_bloqueado(sesion, horario_id: int, fecha: date) -> Turno | None:
    return sesion.scalar(
        select(Turno)
        .where(Turno.horario_id == horario_id, Turno.fecha == fecha)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def materializar_turno(sesion, turno_id: str, zona: ZoneInfo) -> Turno:
    """Devuelve el turno "horarioId:fecha" guardado y bloqueado, y si todavía no existe lo guarda desde la plantilla.

    Al guardarse copia la foto de la versión que rige ese día (D11) y no se recalcula si cambia la plantilla (D12).
    Un turno que la plantilla no produce responde 404 y no guarda nada. Si dos transacciones lo guardan a la
    vez, `ux_turno_horario_fecha` deja una sola fila y la segunda espera a la primera.
    """
    horario_id, fecha = parsear_id_turno(turno_id)
    # Mismos extremos que GET /turnos: más cerca del borde, el cálculo de la plantilla desborda.
    if fecha <= date.min + timedelta(days=1) or fecha >= date.max - timedelta(days=1):
        raise _no_existe(turno_id)
    existente = _buscar_bloqueado(sesion, horario_id, fecha)
    if existente is not None:
        return existente
    calculados = calcular_turnos(versiones_en_rango(sesion, fecha, fecha), fecha, fecha, zona)
    calculado = next((t for t in calculados if t.horario_id == horario_id and t.fecha == fecha), None)
    if calculado is None:
        raise _no_existe(turno_id)
    sesion.execute(
        insert(Turno)
        .values(
            horario_id=horario_id,
            fecha=fecha,
            version_id=calculado.version_id,
            inicio=calculado.inicio,
            fin=calculado.fin,
            titular_id=calculado.titular.id if calculado.titular else None,
        )
        .on_conflict_do_nothing(constraint="ux_turno_horario_fecha")
    )
    return _buscar_bloqueado(sesion, horario_id, fecha)


def bloquear_turnos(sesion, turno_ids: Iterable[str], zona: ZoneInfo) -> list[Turno]:
    """Materializa y bloquea varios turnos por (horario, fecha) ascendente, para que dos lotes no se traben (regla 8)."""
    claves = sorted({parsear_id_turno(turno_id) for turno_id in turno_ids})
    return [materializar_turno(sesion, f"{horario_id}:{fecha.isoformat()}", zona) for horario_id, fecha in claves]

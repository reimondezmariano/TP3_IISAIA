"""Consultas de la consolidación perezosa (D20). No hacen commit."""

from collections.abc import Collection
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modelos import (
    EstadoConsolidacion,
    EstadoUsuario,
    EstadoVacante,
    EventoTurno,
    Notificacion,
    Postulacion,
    Turno,
    Usuario,
    Vacante,
    VersionHorario,
)


def bloquear_marca(sesion: Session) -> date | None:
    """Devuelve la marca y bloquea su fila hasta el fin de la transacción (regla 8). Crea la fila si falta."""
    sesion.execute(insert(EstadoConsolidacion).values(id=1).on_conflict_do_nothing(index_elements=["id"]))
    return sesion.execute(
        select(EstadoConsolidacion.consolidado_hasta).where(EstadoConsolidacion.id == 1).with_for_update()
    ).scalar_one()


def guardar_marca(sesion: Session, fecha: date) -> None:
    sesion.execute(update(EstadoConsolidacion).where(EstadoConsolidacion.id == 1).values(consolidado_hasta=fecha))


def desfase_demo(sesion: Session) -> timedelta:
    """Adelanto del reloj de demo (D27). Sin fila (después del seed) es la hora real."""
    return sesion.scalar(select(EstadoConsolidacion.desfase_demo).where(EstadoConsolidacion.id == 1)) or timedelta(0)


def guardar_desfase_demo(sesion: Session, desfase: timedelta) -> None:
    bloquear_marca(sesion)
    sesion.execute(update(EstadoConsolidacion).where(EstadoConsolidacion.id == 1).values(desfase_demo=desfase))


def hay_historia_despues(sesion: Session, instante: datetime, dia: date) -> bool:
    """¿Se registró algo con el reloj de demo adelantado más allá de `instante`? (marca o instantes de dominio)."""
    return bool(
        sesion.scalar(
            select(
                or_(
                    exists().where(EstadoConsolidacion.consolidado_hasta > dia),
                    exists().where(Turno.consolidado_en > instante),
                    exists().where(EventoTurno.ocurrido_en > instante),
                    exists().where(Notificacion.creada_en > instante),
                    exists().where(Vacante.creada_en > instante),
                    exists().where(Postulacion.creada_en > instante),
                )
            )
        )
    )


def primera_vigencia(sesion: Session) -> date | None:
    return sesion.scalar(select(func.min(VersionHorario.vigente_desde)))


def insertar_consolidados(sesion: Session, filas: list[dict[str, Any]]) -> int:
    """Guarda turnos ya consolidados; si el turno ya tenía fila (D11), no la toca. Devuelve cuántos insertó."""
    if not filas:
        return 0
    insertados = sesion.execute(
        insert(Turno).values(filas).on_conflict_do_nothing(constraint="ux_turno_horario_fecha").returning(Turno.id)
    )
    return len(insertados.all())


def turnos_guardados_por_consolidar(sesion: Session, ahora: datetime) -> list[tuple[Turno, Vacante | None]]:
    """Turnos guardados que terminaron y no se consolidaron, bloqueados por id, con su vacante abierta (bloqueada)."""
    turnos = list(
        sesion.scalars(
            select(Turno)
            .where(Turno.consolidado_en.is_(None), Turno.fin <= ahora)
            .order_by(Turno.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    if not turnos:
        return []
    abiertas = {
        vacante.turno_id: vacante
        for vacante in sesion.scalars(
            select(Vacante)
            .where(Vacante.turno_id.in_([t.id for t in turnos]), Vacante.estado == EstadoVacante.ABIERTA)
            .order_by(Vacante.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    return [(turno, abiertas.get(turno.id)) for turno in turnos]


def fechas_de_baja(sesion: Session, usuario_ids: Collection[int]) -> dict[int, date]:
    """Último día de los usuarios dados de baja entre `usuario_ids` (D24)."""
    if not usuario_ids:
        return {}
    filas = sesion.execute(
        select(Usuario.id, Usuario.fecha_baja).where(Usuario.id.in_(usuario_ids), Usuario.estado == EstadoUsuario.BAJA)
    )
    return {usuario_id: fecha_baja for usuario_id, fecha_baja in filas}

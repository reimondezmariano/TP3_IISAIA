"""Turnos guardados (D09, D11). No hacen commit; trabajan dentro de la transacción de quien llama."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.orm import aliased
from sqlalchemy.dialects.postgresql import insert

from app.dominio.calendario import calcular_turnos, formatear_id_turno, parsear_id_turno
from app.errores import ErrorDominio
from app.modelos import EstadoVacante, Postulacion, Turno, Usuario, Vacante
from app.repos.horarios import TurnoAfectado, _titular, versiones_en_rango


def no_existe(turno_id: str) -> ErrorDominio:
    return ErrorDominio("TURNO_NO_ENCONTRADO", f"No existe el turno {turno_id}.", 404)


def fecha_fuera_de_rango(fecha: date) -> bool:
    """Mismos extremos que GET /turnos: más cerca del borde, el cálculo de la plantilla desborda."""
    return fecha <= date.min + timedelta(days=1) or fecha >= date.max - timedelta(days=1)


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
    if fecha_fuera_de_rango(fecha):
        raise no_existe(turno_id)
    existente = _buscar_bloqueado(sesion, horario_id, fecha)
    if existente is not None:
        return existente
    calculados = calcular_turnos(versiones_en_rango(sesion, fecha, fecha), fecha, fecha, zona)
    calculado = next((t for t in calculados if t.horario_id == horario_id and t.fecha == fecha), None)
    if calculado is None:
        raise no_existe(turno_id)
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


def coberturas_desde(sesion, medico_id: int, desde: date) -> list[Turno]:
    """Turnos que el médico quedó cubriendo desde `desde` y que todavía no se consolidaron (D24).

    Los bloquea por (horario, fecha) ascendente, como `bloquear_turnos` (convención 20).
    """
    return list(
        sesion.scalars(
            select(Turno)
            .where(Turno.asignado_id == medico_id, Turno.fecha >= desde, Turno.consolidado_en.is_(None))
            .order_by(Turno.horario_id, Turno.fecha)
            .with_for_update()
        )
    )


def turno_a_afectado(sesion, turno: Turno, asignado: Usuario | None) -> TurnoAfectado:
    """El turno como `TurnoAfectado`, con el asignado que se indica (por ejemplo, el que tenía antes de reabrirse)."""
    return TurnoAfectado(
        id=formatear_id_turno(turno.horario_id, turno.fecha),
        horario_id=turno.horario_id,
        fecha=turno.fecha,
        inicio=turno.inicio,
        fin=turno.fin,
        titular=_titular(sesion.get(Usuario, turno.titular_id) if turno.titular_id is not None else None),
        asignado=_titular(asignado),
    )


def vacantes_abiertas_en_rango(sesion, desde: date, hasta: date) -> dict[tuple[int, date], tuple[Vacante, Turno, Usuario]]:
    """Vacantes abiertas de turnos guardados que empiezan entre desde-1 y hasta, por (horario_id, fecha).

    El día anterior entra porque un turno nocturno que empieza ayer puede terminar dentro del rango.
    """
    filas = sesion.execute(
        select(Vacante, Turno, Usuario)
        .join(Turno, Vacante.turno_id == Turno.id)
        .join(Usuario, Vacante.generada_por_id == Usuario.id)
        .where(
            Vacante.estado == EstadoVacante.ABIERTA,
            Turno.fecha >= desde - timedelta(days=1),
            Turno.fecha <= hasta,
        )
    ).all()
    return {(turno.horario_id, turno.fecha): (vacante, turno, generador) for vacante, turno, generador in filas}


@dataclass(frozen=True)
class NovedadesTurno:
    asignado: Usuario | None
    sin_cobertura: bool
    postulacion_propia_id: int | None
    cantidad_postulantes: int


def novedades_en_rango(sesion, desde: date, hasta: date, usuario_id: int) -> dict[tuple[int, date], NovedadesTurno]:
    """Asignado vigente, marca de sin cobertura, postulación activa de `usuario_id` y cantidad de postulaciones
    activas de los turnos guardados que empiezan entre desde-1 y hasta, por (horario_id, fecha), en una sola
    consulta. Un turno sin fila no tiene novedades (D11)."""
    asignado = aliased(Usuario)
    activas = aliased(Postulacion)
    cantidad = (
        select(func.count())
        .where(activas.turno_id == Turno.id, activas.retirada_en.is_(None))
        .correlate(Turno)
        .scalar_subquery()
    )
    filas = sesion.execute(
        select(Turno, asignado, Postulacion.id, cantidad)
        .outerjoin(asignado, Turno.asignado_id == asignado.id)
        .outerjoin(
            Postulacion,
            and_(
                Postulacion.turno_id == Turno.id,
                Postulacion.medico_id == usuario_id,
                Postulacion.retirada_en.is_(None),
            ),
        )
        .where(Turno.fecha >= desde - timedelta(days=1), Turno.fecha <= hasta)
    ).all()
    return {
        (turno.horario_id, turno.fecha): NovedadesTurno(
            asignado_db, turno.sin_cobertura_en is not None, postulacion_id, cantidad_postulantes
        )
        for turno, asignado_db, postulacion_id, cantidad_postulantes in filas
    }

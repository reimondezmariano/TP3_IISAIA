"""Guardias de un médico y turnos del mes para la elegibilidad y el orden por equidad (D16, D17). No hacen commit."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.dominio.calendario import calcular_turnos, parsear_id_turno
from app.dominio.consolidacion import realizador_presunto
from app.dominio.elegibilidad import Guardia
from app.dominio.equidad import TurnoDelMes
from app.modelos import EstadoVacante, Turno, Vacante
from app.repos.horarios import versiones_en_rango


def guardias_del_medico(
    sesion: Session, medico_id: int, inicio: datetime, fin: datetime, excluir_turno_id: str, zona: ZoneInfo
) -> list[Guardia]:
    """Guardias que se superponen con [inicio, fin) y que el médico tiene hoy, sin contar el turno evaluado.

    Un turno guardado manda con su foto (D11, D12); uno que nunca se guardó sale de la plantilla. Quién lo tiene
    es el asignado vigente o, si no hay, el titular, salvo con vacante abierta o sin cobertura (D31).
    """
    excluido = parsear_id_turno(excluir_turno_id)
    desde = inicio.astimezone(zona).date() - timedelta(days=1)
    hasta = fin.astimezone(zona).date()
    calculados = calcular_turnos(versiones_en_rango(sesion, desde, hasta), desde, hasta, zona)

    claves = [(t.horario_id, t.fecha) for t in calculados]
    consulta = select(Turno).where(Turno.inicio < fin, Turno.fin > inicio)
    if claves:
        consulta = select(Turno).where(
            (Turno.inicio < fin) & (Turno.fin > inicio) | tuple_(Turno.horario_id, Turno.fecha).in_(claves)
        )
    guardados = {(t.horario_id, t.fecha): t for t in sesion.scalars(consulta)}
    con_vacante = set(
        sesion.scalars(
            select(Vacante.turno_id).where(
                Vacante.turno_id.in_([t.id for t in guardados.values()]), Vacante.estado == EstadoVacante.ABIERTA
            )
        )
    )

    # (clave) -> (inicio, fin, quién lo tiene hoy)
    turnos: dict[tuple[int, date], tuple[datetime, datetime, int | None]] = {}
    for clave, t in guardados.items():
        turnos[clave] = (
            t.inicio,
            t.fin,
            realizador_presunto(t.titular_id, t.asignado_id, t.id in con_vacante, t.sin_cobertura_en is not None),
        )
    for t in calculados:
        turnos.setdefault((t.horario_id, t.fecha), (t.inicio, t.fin, t.titular.id if t.titular else None))

    return [
        Guardia(ini, f)
        for clave, (ini, f, responsable) in sorted(turnos.items(), key=lambda kv: kv[1][0])
        if clave != excluido and responsable == medico_id and ini < fin and f > inicio
    ]


def turnos_del_mes(sesion: Session, anio: int, mes: int, zona: ZoneInfo) -> list[TurnoDelMes]:
    """Turnos guardados cuyo inicio cae en ese mes calendario de la zona del servicio (D17)."""
    primero = datetime.combine(date(anio, mes, 1), time(0), tzinfo=zona)
    siguiente = datetime.combine(date(anio + (mes == 12), mes % 12 + 1, 1), time(0), tzinfo=zona)
    filas = sesion.scalars(select(Turno).where(Turno.inicio >= primero, Turno.inicio < siguiente).order_by(Turno.inicio))
    return [TurnoDelMes(t.inicio, t.asignado_id, t.titular_id) for t in filas]

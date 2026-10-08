from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, time, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.dominio.calendario import Titular, VersionPlantilla
from app.dominio.plantilla import Vigencia
from app.modelos import HorarioPactado, Usuario, VersionHorario


@dataclass(frozen=True)
class DatosVersion:
    medico_id: int | None
    dia_semana: int
    hora_inicio: time
    duracion_horas: int
    frecuencia_semanas: int
    fecha_ancla: date


def crear_horario(
    sesion: Session, datos: DatosVersion, vigente_desde: date, vigente_hasta: date | None = None
) -> HorarioPactado:
    horario = HorarioPactado()
    sesion.add(horario)
    sesion.flush()
    sesion.add(
        VersionHorario(horario_id=horario.id, vigente_desde=vigente_desde, vigente_hasta=vigente_hasta, **asdict(datos))
    )
    sesion.flush()
    return horario


def nueva_version(sesion: Session, horario_id: int, datos: DatosVersion, desde: date) -> VersionHorario:
    """Cierra la versión vigente en `desde` y abre otra desde esa fecha (D10).

    Si la vigente no se puede cerrar en esa fecha, la rechaza la restricción de la base.
    """
    vigente = sesion.scalars(
        select(VersionHorario)
        .where(VersionHorario.horario_id == horario_id, VersionHorario.vigente_hasta.is_(None))
        .with_for_update()
    ).one_or_none()
    if vigente is not None:
        vigente.vigente_hasta = desde
        sesion.flush()
    nueva = VersionHorario(horario_id=horario_id, vigente_desde=desde, vigente_hasta=None, **asdict(datos))
    sesion.add(nueva)
    sesion.flush()
    return nueva


def versiones_en_rango(sesion: Session, desde: date, hasta: date) -> list[VersionPlantilla]:
    """Versiones que rigen algún día entre desde - 1 (turnos que cruzan medianoche) y hasta."""
    rango = func.daterange(desde - timedelta(days=1), hasta + timedelta(days=1), "[)")
    consulta = (
        select(VersionHorario, Usuario)
        .outerjoin(Usuario, VersionHorario.medico_id == Usuario.id)
        .where(VersionHorario.vigencia.op("&&")(rango))
        .order_by(VersionHorario.horario_id, VersionHorario.vigente_desde)
    )
    return [_a_plantilla(version, medico) for version, medico in sesion.execute(consulta).all()]


def _a_plantilla(version: VersionHorario, medico: Usuario | None) -> VersionPlantilla:
    return VersionPlantilla(
        version_id=version.id,
        horario_id=version.horario_id,
        titular=Titular(medico.id, medico.nombre) if medico is not None else None,
        dia_semana=version.dia_semana,
        hora_inicio=version.hora_inicio,
        duracion_horas=version.duracion_horas,
        frecuencia_semanas=version.frecuencia_semanas,
        fecha_ancla=version.fecha_ancla,
        vigente_desde=version.vigente_desde,
        vigente_hasta=version.vigente_hasta,
    )


def _con_versiones():
    return (
        select(HorarioPactado)
        .options(selectinload(HorarioPactado.versiones).selectinload(VersionHorario.medico))
        .execution_options(populate_existing=True)
    )


def listar_horarios(sesion: Session) -> list[HorarioPactado]:
    """Todos los horarios, también los cerrados, con sus versiones ordenadas por vigencia."""
    return list(sesion.scalars(_con_versiones().order_by(HorarioPactado.id)))


def obtener_horario(sesion: Session, horario_id: int) -> HorarioPactado | None:
    return sesion.scalar(_con_versiones().where(HorarioPactado.id == horario_id))


def a_vigencia(version: VersionHorario) -> Vigencia:
    return Vigencia(
        version_id=version.id,
        medico_id=version.medico_id,
        vigente_desde=version.vigente_desde,
        vigente_hasta=version.vigente_hasta,
    )


def versiones_no_terminadas_por_medico(
    sesion: Session, hoy: date, medico_id: int | None = None
) -> dict[int, list[VersionHorario]]:
    """Versiones con titular que rigen hoy o empiezan después, agrupadas por médico."""
    consulta = (
        select(VersionHorario)
        .where(
            VersionHorario.medico_id.is_not(None),
            or_(VersionHorario.vigente_hasta.is_(None), VersionHorario.vigente_hasta > hoy),
        )
        .order_by(VersionHorario.vigente_desde, VersionHorario.horario_id)
    )
    if medico_id is not None:
        consulta = consulta.where(VersionHorario.medico_id == medico_id)
    por_medico: dict[int, list[VersionHorario]] = defaultdict(list)
    for version in sesion.scalars(consulta):
        por_medico[version.medico_id].append(version)
    return por_medico

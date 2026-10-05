from dataclasses import asdict, dataclass
from datetime import date, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dominio.calendario import Titular, VersionPlantilla
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

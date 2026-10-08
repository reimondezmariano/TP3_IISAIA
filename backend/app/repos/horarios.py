from collections import defaultdict
from collections.abc import Collection
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.dominio.calendario import Titular, VersionPlantilla, formatear_id_turno
from app.dominio.plantilla import Vigencia
from app.modelos import HorarioPactado, Turno, Usuario, VersionHorario


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
    """Parte en `desde` la versión que rige ese día y abre otra que hereda su fin de vigencia (D10).

    Si ninguna rige ese día, abre una sin fin. Las reglas están en app/dominio/plantilla.py; si igual
    choca, la rechazan las restricciones de la base.
    """
    cubre = sesion.scalars(
        select(VersionHorario)
        .where(
            VersionHorario.horario_id == horario_id,
            VersionHorario.vigente_desde <= desde,
            or_(VersionHorario.vigente_hasta.is_(None), VersionHorario.vigente_hasta > desde),
        )
        .with_for_update()
    ).one_or_none()
    hasta = None
    if cubre is not None:
        hasta = cubre.vigente_hasta
        cubre.vigente_hasta = desde
        sesion.flush()
    nueva = VersionHorario(horario_id=horario_id, vigente_desde=desde, vigente_hasta=hasta, **asdict(datos))
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


def datos_de(version: VersionHorario) -> DatosVersion:
    return DatosVersion(
        medico_id=version.medico_id,
        dia_semana=version.dia_semana,
        hora_inicio=version.hora_inicio,
        duracion_horas=version.duracion_horas,
        frecuencia_semanas=version.frecuencia_semanas,
        fecha_ancla=version.fecha_ancla,
    )


def bloquear_horario(sesion: Session, horario_id: int) -> list[VersionHorario] | None:
    """Bloquea el horario hasta el fin de la transacción y devuelve sus versiones releídas (regla 8).

    Bloquear la fila de horario_pactado, y no las versiones, serializa también a quien va a insertar
    una versión nueva: al despertar, el SELECT de versiones ya ve lo que confirmó el otro.
    """
    existe = sesion.scalar(select(HorarioPactado.id).where(HorarioPactado.id == horario_id).with_for_update())
    if existe is None:
        return None
    return list(
        sesion.scalars(
            select(VersionHorario)
            .where(VersionHorario.horario_id == horario_id)
            .order_by(VersionHorario.vigente_desde)
            .execution_options(populate_existing=True)
        )
    )


def modificar_version(sesion: Session, version: VersionHorario, datos: DatosVersion) -> VersionHorario:
    """Reemplaza los datos de una versión que todavía no rige (D10): no cambia su vigencia."""
    for campo, valor in asdict(datos).items():
        setattr(version, campo, valor)
    sesion.flush()
    return version


@dataclass(frozen=True)
class TurnoAfectado:
    id: str
    horario_id: int
    fecha: date
    inicio: datetime
    fin: datetime
    titular: Titular | None
    asignado: Titular | None


def _titular(usuario: Usuario | None) -> Titular | None:
    return Titular(usuario.id, usuario.nombre) if usuario is not None else None


def turnos_afectados(sesion: Session, horario_ids: Collection[int], desde: date) -> list[TurnoAfectado]:
    """Turnos ya guardados desde `desde` y sin consolidar: conservan su foto aunque cambie la plantilla (D11, D12)."""
    if not horario_ids:
        return []
    titular = aliased(Usuario)
    asignado = aliased(Usuario)
    consulta = (
        select(Turno, titular, asignado)
        .outerjoin(titular, Turno.titular_id == titular.id)
        .outerjoin(asignado, Turno.asignado_id == asignado.id)
        .where(Turno.horario_id.in_(horario_ids), Turno.fecha >= desde, Turno.consolidado_en.is_(None))
        .order_by(Turno.inicio, Turno.horario_id)
    )
    return [
        TurnoAfectado(
            id=formatear_id_turno(turno.horario_id, turno.fecha),
            horario_id=turno.horario_id,
            fecha=turno.fecha,
            inicio=turno.inicio,
            fin=turno.fin,
            titular=_titular(t),
            asignado=_titular(a),
        )
        for turno, t, a in sesion.execute(consulta).all()
    ]


def versiones_del_medico_desde(sesion: Session, medico_id: int, desde: date) -> list[VersionHorario]:
    """Versiones del médico que rigen en `desde` o después."""
    return list(
        sesion.scalars(
            select(VersionHorario)
            .where(
                VersionHorario.medico_id == medico_id,
                or_(VersionHorario.vigente_hasta.is_(None), VersionHorario.vigente_hasta > desde),
            )
            .order_by(VersionHorario.horario_id, VersionHorario.vigente_desde)
        )
    )

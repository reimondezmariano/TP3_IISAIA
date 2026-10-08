from datetime import date, datetime, time

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import requiere_coordinador
from app.db import get_db
from app.dominio.calendario import Titular
from app.dominio.plantilla import EstadoHorario, estado_horario, lunes_de
from app.modelos import HorarioPactado, Usuario, VersionHorario
from app.reloj import Reloj, get_reloj, hoy
from app.repos.horarios import DatosVersion, a_vigencia, listar_horarios, obtener_horario
from app.servicios.plantilla import crear_horario_pactado

router = APIRouter()


class PersonaOut(Esquema):
    id: int
    nombre: str


class VersionOut(Esquema):
    id: int
    medico: PersonaOut | None
    dia_semana: int
    hora_inicio: time
    duracion_horas: int
    frecuencia_semanas: int
    fecha_ancla: date
    vigente_desde: date
    vigente_hasta: date | None


class HorarioOut(Esquema):
    id: int
    estado: EstadoHorario
    versiones: list[VersionOut]


def persona_out(persona: Usuario | Titular | None) -> PersonaOut | None:
    return PersonaOut(id=persona.id, nombre=persona.nombre) if persona is not None else None


def version_out(version: VersionHorario) -> VersionOut:
    return VersionOut(
        id=version.id,
        medico=persona_out(version.medico),
        dia_semana=version.dia_semana,
        hora_inicio=version.hora_inicio,
        duracion_horas=version.duracion_horas,
        frecuencia_semanas=version.frecuencia_semanas,
        fecha_ancla=version.fecha_ancla,
        vigente_desde=version.vigente_desde,
        vigente_hasta=version.vigente_hasta,
    )


def horario_out(horario: HorarioPactado, dia: date) -> HorarioOut:
    return HorarioOut(
        id=horario.id,
        estado=estado_horario([a_vigencia(v) for v in horario.versiones], dia),
        versiones=[version_out(v) for v in horario.versiones],
    )


@router.get("/horarios", response_model=list[HorarioOut])
def listar(
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> list[HorarioOut]:
    """Plantilla completa con su historia de versiones (D10) y el estado calculado para hoy (D24)."""
    dia = hoy(reloj)
    return [horario_out(h, dia) for h in listar_horarios(db)]


class HorarioIn(Esquema):
    medico_id: int
    dia_semana: int = Field(ge=1, le=7)
    hora_inicio: time
    duracion_horas: int = Field(ge=1, le=24)
    frecuencia_semanas: int = Field(default=1, ge=1, le=52)
    fecha_ancla: date | None = None  # vacía: el lunes de la semana de vigenteDesde (D14)
    vigente_desde: date


@router.post("/horarios", response_model=HorarioOut, status_code=201)
def crear(
    datos: HorarioIn,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> HorarioOut:
    """Carga un horario pactado con su primera versión (D10). El titular tiene que ser un médico activo."""
    dia = hoy(reloj)
    version = DatosVersion(
        medico_id=datos.medico_id,
        dia_semana=datos.dia_semana,
        hora_inicio=datos.hora_inicio,
        duracion_horas=datos.duracion_horas,
        frecuencia_semanas=datos.frecuencia_semanas,
        fecha_ancla=datos.fecha_ancla or lunes_de(datos.vigente_desde),
    )
    horario = crear_horario_pactado(db, version, datos.vigente_desde, dia)
    db.commit()
    return horario_out(obtener_horario(db, horario.id), dia)

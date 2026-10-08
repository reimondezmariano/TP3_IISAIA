from datetime import date, datetime, time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import requiere_coordinador
from app.db import get_db
from app.dominio.calendario import Titular
from app.dominio.plantilla import EstadoHorario, estado_horario
from app.modelos import HorarioPactado, Usuario, VersionHorario
from app.reloj import Reloj, get_reloj, hoy
from app.repos.horarios import a_vigencia, listar_horarios

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

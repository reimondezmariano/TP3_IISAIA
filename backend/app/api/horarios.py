from datetime import date, datetime, time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import Field, model_validator
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import requiere_coordinador
from app.config import get_settings
from app.db import get_db
from app.dominio.calendario import Titular
from app.dominio.plantilla import EstadoHorario, estado_horario, lunes_de
from app.modelos import HorarioPactado, Usuario, VersionHorario
from app.reloj import Reloj, get_reloj, hoy
from app.repos.horarios import DatosVersion, TurnoAfectado, a_vigencia, listar_horarios, obtener_horario
from app.servicios.plantilla import abrir_version, cerrar_horario, crear_horario_pactado

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
    horario = crear_horario_pactado(db, version, datos.vigente_desde, dia, reloj.ahora(), get_settings().zona)
    db.commit()
    return horario_out(obtener_horario(db, horario.id), dia)


class TurnoAfectadoOut(Esquema):
    id: str
    horario_id: int
    fecha: date
    inicio: datetime
    fin: datetime
    titular: PersonaOut | None
    asignado: PersonaOut | None


def turno_afectado_out(turno: TurnoAfectado) -> TurnoAfectadoOut:
    zona = get_settings().zona
    return TurnoAfectadoOut(
        id=turno.id,
        horario_id=turno.horario_id,
        fecha=turno.fecha,
        inicio=turno.inicio.astimezone(zona),
        fin=turno.fin.astimezone(zona),
        titular=persona_out(turno.titular),
        asignado=persona_out(turno.asignado),
    )


class VersionIn(Esquema):
    """Solo lo que cambia; lo omitido se copia de la versión que rige en `desde`. medicoId null = sin titular."""

    desde: date
    medico_id: int | None = None
    dia_semana: int | None = Field(default=None, ge=1, le=7)
    hora_inicio: time | None = None
    duracion_horas: int | None = Field(default=None, ge=1, le=24)
    frecuencia_semanas: int | None = Field(default=None, ge=1, le=52)
    fecha_ancla: date | None = None

    @model_validator(mode="after")
    def _solo_el_medico_admite_null(self) -> "VersionIn":
        nulos = sorted(c for c in self.model_fields_set if c != "medico_id" and getattr(self, c) is None)
        if nulos:
            raise ValueError(f"Solo medicoId admite null; vinieron en null: {', '.join(nulos)}")
        return self

    def cambios(self) -> dict[str, Any]:
        return {campo: getattr(self, campo) for campo in self.model_fields_set if campo != "desde"}


class VersionNuevaOut(Esquema):
    version: VersionOut
    turnos_afectados: list[TurnoAfectadoOut]


@router.post("/horarios/{horario_id}/versiones", response_model=VersionNuevaOut, status_code=201)
def nueva(
    horario_id: int,
    datos: VersionIn,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> VersionNuevaOut:
    """Modifica un horario o designa su titular con una versión nueva (D10, D24) y lista los turnos afectados (D12)."""
    resultado = abrir_version(
        db, horario_id, datos.cambios(), datos.desde, hoy(reloj), reloj.ahora(), get_settings().zona
    )
    db.commit()
    return VersionNuevaOut(
        version=version_out(resultado.version),
        turnos_afectados=[turno_afectado_out(t) for t in resultado.turnos_afectados],
    )


class CierreIn(Esquema):
    desde: date  # primer día en que el horario ya no rige


class CierreOut(Esquema):
    horario: HorarioOut
    turnos_afectados: list[TurnoAfectadoOut]


@router.post("/horarios/{horario_id}/cierre", response_model=CierreOut)
def cerrar(
    horario_id: int,
    datos: CierreIn,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> CierreOut:
    """Cierra un horario pactado (D24) y lista los turnos ya guardados que quedan afuera (D12)."""
    dia = hoy(reloj)
    afectados = cerrar_horario(db, horario_id, datos.desde, dia, reloj.ahora(), get_settings().zona)
    db.commit()
    return CierreOut(
        horario=horario_out(obtener_horario(db, horario_id), dia),
        turnos_afectados=[turno_afectado_out(t) for t in afectados],
    )

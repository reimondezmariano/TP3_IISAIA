from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import usuario_actual
from app.config import get_settings
from app.db import get_db
from app.dominio.calendario import TurnoCalculado, calcular_turnos
from app.errores import ErrorDominio
from app.modelos import Usuario
from app.reloj import Reloj, get_reloj
from app.repos.horarios import versiones_en_rango
from app.servicios.consolidacion import ponerse_al_dia

router = APIRouter()

MAX_DIAS_RANGO = 62


class TitularOut(Esquema):
    id: int
    nombre: str


class TurnoOut(Esquema):
    id: str
    horario_id: int
    fecha: date
    inicio: datetime
    fin: datetime
    duracion_horas: int
    titular: TitularOut | None


def _a_salida(turno: TurnoCalculado) -> TurnoOut:
    titular = TitularOut(id=turno.titular.id, nombre=turno.titular.nombre) if turno.titular else None
    return TurnoOut(
        id=turno.id,
        horario_id=turno.horario_id,
        fecha=turno.fecha,
        inicio=turno.inicio,
        fin=turno.fin,
        duracion_horas=turno.duracion_horas,
        titular=titular,
    )


@router.get("/turnos", response_model=list[TurnoOut])
def listar_turnos(
    desde: date,
    hasta: date,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _usuario: Usuario = Depends(usuario_actual),
) -> list[TurnoOut]:
    """Turnos cuyo intervalo se superpone con [desde 00:00, hasta 24:00) en la zona del servicio (D09, D11)."""
    if hasta < desde:
        raise ErrorDominio("RANGO_INVALIDO", "La fecha 'hasta' no puede ser anterior a 'desde'.")
    if (hasta - desde).days + 1 > MAX_DIAS_RANGO:
        raise ErrorDominio("RANGO_DEMASIADO_GRANDE", f"El rango no puede superar {MAX_DIAS_RANGO} días.")
    if desde <= date.min + timedelta(days=1) or hasta >= date.max - timedelta(days=1):
        raise ErrorDominio("FECHA_FUERA_DE_RANGO", "Las fechas deben estar lejos de los extremos del calendario (años 1 y 9999).")
    zona = get_settings().zona
    # D20: la consolidación es perezosa; se hace antes de responder el calendario y se confirma aparte.
    ponerse_al_dia(db, reloj, zona)
    db.commit()
    versiones = versiones_en_rango(db, desde, hasta)
    turnos = calcular_turnos(versiones, desde, hasta, zona)
    return [_a_salida(turno) for turno in turnos]

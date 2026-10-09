from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.api.esquemas_operacion import PersonaOut
from app.auth import usuario_actual
from app.config import get_settings
from app.db import get_db
from app.dominio.calendario import TurnoCalculado, calcular_turnos
from app.dominio.vacantes import es_urgente
from app.errores import ErrorDominio
from app.modelos import Turno, Usuario, Vacante
from app.reloj import Reloj, get_reloj
from app.repos.horarios import versiones_en_rango
from app.repos.turnos import NovedadesTurno, novedades_en_rango, vacantes_abiertas_en_rango
from app.servicios.consolidacion import ponerse_al_dia

router = APIRouter()

MAX_DIAS_RANGO = 62


class TitularOut(Esquema):
    id: int
    nombre: str


class VacanteAbiertaOut(Esquema):
    """Resumen de la vacante abierta de un turno. El motivo no va acá (D25): está en POST/GET de vacantes."""

    id: int
    urgente: bool
    generada_por: PersonaOut


class TurnoOut(Esquema):
    id: str
    horario_id: int
    fecha: date
    inicio: datetime
    fin: datetime
    duracion_horas: int
    titular: TitularOut | None
    vacante: VacanteAbiertaOut | None
    asignado: PersonaOut | None  # quien cubre el turno hoy (D08 punto 4); null si no hay
    sin_cobertura: bool  # el coordinador lo marcó sin cobertura, o se consolidó con la vacante abierta (D19)
    mi_postulacion_id: int | None  # postulación activa de quien consulta, para retirarla (D16)
    cantidad_postulantes: int  # postulaciones activas del turno, de cualquier médico (D34)


SIN_NOVEDADES = NovedadesTurno(asignado=None, sin_cobertura=False, postulacion_propia_id=None, cantidad_postulantes=0)


def _a_salida(
    turno: TurnoCalculado, abierta: tuple[Vacante, Turno, Usuario] | None, novedades: NovedadesTurno
) -> TurnoOut:
    titular = TitularOut(id=turno.titular.id, nombre=turno.titular.nombre) if turno.titular else None
    vacante = None
    if abierta is not None:
        vacante_db, turno_db, generador = abierta
        vacante = VacanteAbiertaOut(
            id=vacante_db.id,
            urgente=es_urgente(turno_db.inicio, vacante_db.creada_en),
            generada_por=PersonaOut(id=generador.id, nombre=generador.nombre),
        )
    return TurnoOut(
        id=turno.id,
        horario_id=turno.horario_id,
        fecha=turno.fecha,
        inicio=turno.inicio,
        fin=turno.fin,
        duracion_horas=turno.duracion_horas,
        titular=titular,
        vacante=vacante,
        asignado=PersonaOut(id=novedades.asignado.id, nombre=novedades.asignado.nombre) if novedades.asignado else None,
        sin_cobertura=novedades.sin_cobertura,
        mi_postulacion_id=novedades.postulacion_propia_id,
        cantidad_postulantes=novedades.cantidad_postulantes,
    )


@router.get("/turnos", response_model=list[TurnoOut])
def listar_turnos(
    desde: date,
    hasta: date,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    usuario: Usuario = Depends(usuario_actual),
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
    abiertas = vacantes_abiertas_en_rango(db, desde, hasta)
    novedades = novedades_en_rango(db, desde, hasta, usuario.id)
    return [
        _a_salida(
            turno,
            abiertas.get((turno.horario_id, turno.fecha)),
            novedades.get((turno.horario_id, turno.fecha), SIN_NOVEDADES),
        )
        for turno in turnos
    ]

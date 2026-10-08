from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import requiere_coordinador
from app.config import get_settings
from app.db import get_db
from app.dominio.calendario import formatear_id_turno
from app.dominio.indicadores import meses_del_rango, primer_dia, primer_dia_siguiente
from app.modelos import Usuario
from app.reloj import Reloj, get_reloj
from app.repos.indicadores import sin_cobertura_por_mes
from app.servicios.consolidacion import consolidar_pendientes, ponerse_al_dia
from app.servicios.sin_cobertura import marcar_sin_cobertura

router = APIRouter()


class PuestaAlDiaOut(Esquema):
    consolidados: int
    vacantes_sin_cobertura: int
    alertas: int


@router.post("/consolidacion", response_model=PuestaAlDiaOut)
def forzar_consolidacion(
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> PuestaAlDiaOut:
    """Consolida los turnos terminados y emite las alertas pendientes ahora mismo (D19, D20). Idempotente."""
    resultado = ponerse_al_dia(db, reloj, get_settings().zona)
    db.commit()
    return PuestaAlDiaOut(
        consolidados=resultado.consolidados,
        vacantes_sin_cobertura=resultado.vacantes_sin_cobertura,
        alertas=resultado.alertas,
    )


class SinCoberturaOut(Esquema):
    turno_id: str
    sin_cobertura_en: datetime
    vacante_id: int


@router.post("/turnos/{turno_id}/sin-cobertura", response_model=SinCoberturaOut)
def sin_cobertura(
    turno_id: str,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    coordinador: Usuario = Depends(requiere_coordinador),
) -> SinCoberturaOut:
    """Nadie cubre la vacante y el turno ya empezó: se consolidará sin realizador (D19)."""
    zona = get_settings().zona
    turno, vacante = marcar_sin_cobertura(db, turno_id, coordinador, reloj, zona)
    db.commit()
    return SinCoberturaOut(
        turno_id=formatear_id_turno(turno.horario_id, turno.fecha),
        sin_cobertura_en=turno.sin_cobertura_en.astimezone(zona),
        vacante_id=vacante.id,
    )


PATRON_MES = r"^(19|20)\d{2}-(0[1-9]|1[0-2])$"


class IndicadorMesOut(Esquema):
    mes: str
    horas: float
    turnos: int


@router.get("/indicadores/sin-cobertura", response_model=list[IndicadorMesOut])
def indicador_sin_cobertura(
    desde: str = Query(pattern=PATRON_MES),
    hasta: str = Query(pattern=PATRON_MES),
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> list[IndicadorMesOut]:
    """Horas sin cobertura por mes (D19): turnos consolidados sin realizador, incluidos los BAJA sin cubrir (D24)."""
    meses = meses_del_rango(desde, hasta)
    consolidar_pendientes(db, reloj, get_settings().zona)
    db.commit()
    datos = sin_cobertura_por_mes(db, primer_dia(meses[0]), primer_dia_siguiente(meses[-1]))
    salida = []
    for mes in meses:
        horas, turnos = datos.get(mes, (0.0, 0))
        salida.append(IndicadorMesOut(mes=mes, horas=horas, turnos=turnos))
    return salida

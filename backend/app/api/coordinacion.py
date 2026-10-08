from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import requiere_coordinador
from app.config import get_settings
from app.db import get_db
from app.dominio.calendario import formatear_id_turno
from app.modelos import Usuario
from app.reloj import Reloj, get_reloj
from app.servicios.consolidacion import ponerse_al_dia
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

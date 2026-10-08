from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import requiere_coordinador
from app.config import get_settings
from app.db import get_db
from app.modelos import Usuario
from app.reloj import Reloj, get_reloj
from app.servicios.consolidacion import ponerse_al_dia

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

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.esquemas_operacion import AsignacionOut, AsignarIn, PersonaOut
from app.api.vacantes import vacante_out
from app.auth import requiere_coordinador
from app.config import get_settings
from app.db import get_db
from app.modelos import Usuario
from app.reloj import Reloj, get_reloj
from app.servicios.asignacion import asignar

router = APIRouter()


@router.put("/turnos/{turno_id}/asignacion", response_model=AsignacionOut)
def asignacion(
    turno_id: str,
    datos: AsignarIn,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    coordinador: Usuario = Depends(requiere_coordinador),
) -> AsignacionOut:
    """Esta persona cubre este turno: elección de un candidato, asignación directa o reasignación (D18)."""
    resultado = asignar(db, turno_id, datos.medico_id, datos.reasignar, coordinador, reloj, get_settings().zona)
    db.commit()
    return AsignacionOut(
        turno_id=turno_id,
        asignado=PersonaOut(id=resultado.asignado.id, nombre=resultado.asignado.nombre),
        caso=resultado.caso,
        vacante=(
            vacante_out(db, resultado.vacante, resultado.turno, coordinador) if resultado.vacante is not None else None
        ),
    )

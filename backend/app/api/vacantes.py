from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.esquemas_operacion import GenerarVacanteIn, LoteVacantesIn, LoteVacantesOut, PersonaOut, VacanteOut
from app.auth import requiere_coordinador, usuario_actual
from app.config import get_settings
from app.db import get_db
from app.dominio.calendario import formatear_id_turno
from app.dominio.vacantes import es_urgente
from app.modelos import RolUsuario, Turno, Usuario, Vacante
from app.reloj import Reloj, get_reloj
from app.servicios.vacantes import generar_lote, generar_vacante, retirar_vacante

router = APIRouter()


def vacante_out(db: Session, vacante: Vacante, turno: Turno, lector: Usuario) -> VacanteOut:
    """Respuesta del contrato. El motivo solo lo ven los coordinadores (D25)."""
    generador = db.get(Usuario, vacante.generada_por_id)
    return VacanteOut(
        id=vacante.id,
        turno_id=formatear_id_turno(turno.horario_id, turno.fecha),
        estado=vacante.estado,
        urgente=es_urgente(turno.inicio, vacante.creada_en),
        motivo=vacante.motivo if lector.rol == RolUsuario.COORDINADOR else None,
        generada_por=PersonaOut(id=generador.id, nombre=generador.nombre),
        creada_en=vacante.creada_en,
        cerrada_en=vacante.cerrada_en,
    )


@router.post("/turnos/{turno_id}/vacantes", response_model=VacanteOut, status_code=201)
def generar(
    turno_id: str,
    datos: GenerarVacanteIn,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    usuario: Usuario = Depends(usuario_actual),
) -> VacanteOut:
    """Genera una vacante sobre el turno (D15). La puede generar el titular, el asignado o un coordinador."""
    resultado = generar_vacante(db, turno_id, usuario, datos.motivo, reloj, get_settings().zona)
    db.commit()
    return vacante_out(db, resultado.vacante, resultado.turno, usuario)


@router.post("/vacantes/lote", response_model=LoteVacantesOut, status_code=201)
def lote(
    datos: LoteVacantesIn,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    coordinador: Usuario = Depends(requiere_coordinador),
) -> LoteVacantesOut:
    """Una vacante por turno, todo o nada, hasta 31 turnos (D15)."""
    resultados = generar_lote(db, datos.turno_ids, coordinador, datos.motivo, reloj, get_settings().zona)
    db.commit()
    return LoteVacantesOut(vacantes=[vacante_out(db, r.vacante, r.turno, coordinador) for r in resultados])


@router.post("/vacantes/{vacante_id}/retiro", response_model=VacanteOut)
def retiro(
    vacante_id: int,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    usuario: Usuario = Depends(usuario_actual),
) -> VacanteOut:
    """Retira una vacante abierta: quien la generó o un coordinador (D15)."""
    vacante = retirar_vacante(db, vacante_id, usuario, reloj)
    db.commit()
    return vacante_out(db, vacante, db.get(Turno, vacante.turno_id), usuario)

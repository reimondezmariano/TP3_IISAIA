from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.esquemas_operacion import CandidatoOut, CandidatosOut, PersonaOut, PostulacionOut
from app.auth import requiere_coordinador, usuario_actual
from app.config import get_settings
from app.db import get_db
from app.dominio.calendario import formatear_id_turno
from app.modelos import Postulacion, Turno, Usuario
from app.reloj import Reloj, get_reloj
from app.servicios.postulaciones import listar_candidatos, postular, retirar_postulacion

router = APIRouter()


def postulacion_out(db: Session, postulacion: Postulacion) -> PostulacionOut:
    turno = db.get(Turno, postulacion.turno_id)
    medico = db.get(Usuario, postulacion.medico_id)
    return PostulacionOut(
        id=postulacion.id,
        turno_id=formatear_id_turno(turno.horario_id, turno.fecha),
        medico=PersonaOut(id=medico.id, nombre=medico.nombre),
        creada_en=postulacion.creada_en,
        retirada_en=postulacion.retirada_en,
    )


@router.post("/turnos/{turno_id}/postulaciones", response_model=PostulacionOut, status_code=201)
def postularse(
    turno_id: str,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    usuario: Usuario = Depends(usuario_actual),
) -> PostulacionOut:
    """Oferta del médico para cubrir el turno (D16). Vale hasta que el turno empiece o la retire."""
    postulacion = postular(db, turno_id, usuario, reloj, get_settings().zona)
    db.commit()
    return postulacion_out(db, postulacion)


@router.post("/postulaciones/{postulacion_id}/retiro", response_model=PostulacionOut)
def retirar(
    postulacion_id: int,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    usuario: Usuario = Depends(usuario_actual),
) -> PostulacionOut:
    """Retira la postulación: su dueño o un coordinador (D16)."""
    postulacion = retirar_postulacion(db, postulacion_id, usuario, reloj)
    db.commit()
    return postulacion_out(db, postulacion)


@router.get("/turnos/{turno_id}/candidatos", response_model=CandidatosOut)
def candidatos(
    turno_id: str,
    db: Session = Depends(get_db),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> CandidatosOut:
    """Candidatos ordenados por equidad: primero quien cubrió menos en el mes del turno (D17)."""
    resultado = listar_candidatos(db, turno_id, get_settings().zona)
    return CandidatosOut(
        turno_id=resultado.turno_id,
        mes=resultado.mes,
        candidatos=[
            CandidatoOut(
                posicion=c.posicion,
                medico=PersonaOut(id=c.medico.id, nombre=c.medico.nombre),
                postulado_en=c.postulado_en,
                coberturas_mes=c.coberturas_mes,
                horas_semana=c.horas_semana,
                elegible=c.elegible,
                motivo_inelegibilidad=c.motivo,
            )
            for c in resultado.candidatos
        ],
    )

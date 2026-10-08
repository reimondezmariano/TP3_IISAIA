"""Rutas de vacantes, postulaciones, candidatos y asignación con respuestas de ejemplo.

Publican el contrato para que la interfaz se conecte antes de que exista la lógica (D15 a D18). No leen ni
escriben la base: devuelven el ejemplo de app/api/esquemas_operacion.py con el encabezado
`X-Respuesta-Ejemplo: true`. Cada ruta se reemplaza por la real en las etapas 2 y 3 del plan.
"""

from fastapi import APIRouter, Depends, Response

from app.api.esquemas_operacion import (
    EJEMPLOS,
    AsignacionOut,
    AsignarIn,
    CandidatosOut,
    GenerarVacanteIn,
    LoteVacantesIn,
    LoteVacantesOut,
    PostulacionOut,
    VacanteOut,
)
from app.auth import requiere_coordinador, usuario_actual
from app.dominio.calendario import parsear_id_turno
from app.modelos import Usuario

router = APIRouter()

ENCABEZADO_EJEMPLO = "X-Respuesta-Ejemplo"


def _ejemplo(respuesta: Response, nombre: str):
    respuesta.headers[ENCABEZADO_EJEMPLO] = "true"
    return EJEMPLOS[nombre]


@router.post("/turnos/{turno_id}/vacantes", response_model=VacanteOut, status_code=201)
def generar_vacante(
    turno_id: str,
    datos: GenerarVacanteIn,
    respuesta: Response,
    _usuario: Usuario = Depends(usuario_actual),
) -> VacanteOut:
    """Genera una vacante sobre el turno (D15). La puede generar el titular, el asignado o un coordinador."""
    parsear_id_turno(turno_id)
    return _ejemplo(respuesta, "VacanteOut")


@router.post("/vacantes/lote", response_model=LoteVacantesOut, status_code=201)
def generar_lote(
    datos: LoteVacantesIn,
    respuesta: Response,
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> LoteVacantesOut:
    """Una vacante por turno, todo o nada, hasta 31 turnos (D15)."""
    for turno_id in datos.turno_ids:
        parsear_id_turno(turno_id)
    return _ejemplo(respuesta, "LoteVacantesOut")


@router.post("/vacantes/{vacante_id}/retiro", response_model=VacanteOut)
def retirar_vacante(
    vacante_id: int, respuesta: Response, _usuario: Usuario = Depends(usuario_actual)
) -> VacanteOut:
    """Retira una vacante abierta: quien la generó o un coordinador (D15)."""
    return _ejemplo(respuesta, "VacanteOut")


@router.post("/turnos/{turno_id}/postulaciones", response_model=PostulacionOut, status_code=201)
def postularse(
    turno_id: str, respuesta: Response, _usuario: Usuario = Depends(usuario_actual)
) -> PostulacionOut:
    """Oferta del médico para cubrir el turno (D16)."""
    parsear_id_turno(turno_id)
    return _ejemplo(respuesta, "PostulacionOut")


@router.post("/postulaciones/{postulacion_id}/retiro", response_model=PostulacionOut)
def retirar_postulacion(
    postulacion_id: int, respuesta: Response, _usuario: Usuario = Depends(usuario_actual)
) -> PostulacionOut:
    """Retira la postulación: su dueño o un coordinador (D16)."""
    return _ejemplo(respuesta, "PostulacionOut")


@router.get("/turnos/{turno_id}/candidatos", response_model=CandidatosOut)
def candidatos(
    turno_id: str, respuesta: Response, _coordinador: Usuario = Depends(requiere_coordinador)
) -> CandidatosOut:
    """Candidatos ordenados por equidad: primero quien cubrió menos en el mes del turno (D17)."""
    parsear_id_turno(turno_id)
    return _ejemplo(respuesta, "CandidatosOut")


@router.put("/turnos/{turno_id}/asignacion", response_model=AsignacionOut)
def asignar(
    turno_id: str,
    datos: AsignarIn,
    respuesta: Response,
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> AsignacionOut:
    """Esta persona cubre este turno: elección de un candidato, asignación directa o reasignación (D18)."""
    parsear_id_turno(turno_id)
    return _ejemplo(respuesta, "AsignacionOut")

"""Contrato de la API de operación: vacantes, postulaciones, candidatos y asignación (D15 a D18, D31).

Los EJEMPLOS son respuestas válidas de cada esquema: el OpenAPI de /docs los muestra. En la etapa 1 las rutas
los devolvían con el encabezado `X-Respuesta-Ejemplo: true`; desde la etapa 3 todas las rutas son reales.
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import Field

from app.api.esquemas import Esquema
from app.dominio.asignacion import CasoAsignacion
from app.dominio.elegibilidad import Motivo
from app.modelos import EstadoVacante

_ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


class PersonaOut(Esquema):
    id: int
    nombre: str


class VacanteOut(Esquema):
    id: int
    turno_id: str  # "horarioId:fecha" (D09)
    estado: EstadoVacante
    urgente: bool  # se calcula: menos de 24 h entre la creación y el inicio del turno (D15)
    motivo: str | None  # solo lo ven los coordinadores (D25); para el resto, null
    generada_por: PersonaOut
    creada_en: datetime
    cerrada_en: datetime | None


class GenerarVacanteIn(Esquema):
    motivo: str | None = None


class LoteVacantesIn(Esquema):
    turno_ids: list[str] = Field(min_length=1, max_length=31)
    motivo: str | None = None


class LoteVacantesOut(Esquema):
    vacantes: list[VacanteOut]


class PostulacionOut(Esquema):
    id: int
    turno_id: str
    medico: PersonaOut
    creada_en: datetime
    retirada_en: datetime | None


class CandidatoOut(Esquema):
    posicion: int | None  # 1..n entre los elegibles (D17); null si no es elegible
    medico: PersonaOut
    postulado_en: datetime
    coberturas_mes: int
    horas_semana: float  # informativo: no altera el orden (D17)
    elegible: bool
    motivo_inelegibilidad: Motivo | None


class CandidatosOut(Esquema):
    turno_id: str
    mes: str  # "AAAA-MM": el mes calendario del turno, sobre el que se cuentan las coberturas
    candidatos: list[CandidatoOut]


class AsignarIn(Esquema):
    medico_id: int
    reasignar: bool = False


class AsignacionOut(Esquema):
    turno_id: str
    asignado: PersonaOut
    caso: CasoAsignacion
    vacante: VacanteOut | None  # la vacante que se cerró, si había


def _instante(dia: int, hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 10, dia, hora, minuto, tzinfo=_ZONA)


_FLORENCIA = PersonaOut(id=1, nombre="Florencia Lucca")
_MARIANO = PersonaOut(id=2, nombre="Mariano Reimondez")
_CARLOS = PersonaOut(id=3, nombre="Carlos Lugones")
_TURNO = "7:2026-10-17"

_VACANTE_ABIERTA = VacanteOut(
    id=12,
    turno_id=_TURNO,
    estado=EstadoVacante.ABIERTA,
    urgente=True,
    motivo="Urgencia familiar",
    generada_por=_FLORENCIA,
    creada_en=_instante(16, 20),
    cerrada_en=None,
)

EJEMPLOS: dict[str, Any] = {
    "VacanteOut": _VACANTE_ABIERTA,
    "LoteVacantesOut": LoteVacantesOut(
        vacantes=[
            _VACANTE_ABIERTA,
            _VACANTE_ABIERTA.model_copy(update={"id": 13, "turno_id": "7:2026-10-24", "urgente": False}),
        ]
    ),
    "PostulacionOut": PostulacionOut(
        id=31, turno_id=_TURNO, medico=_MARIANO, creada_en=_instante(16, 21), retirada_en=None
    ),
    "CandidatosOut": CandidatosOut(
        turno_id=_TURNO,
        mes="2026-10",
        candidatos=[
            CandidatoOut(
                posicion=1,
                medico=_MARIANO,
                postulado_en=_instante(16, 21),
                coberturas_mes=0,
                horas_semana=12.0,
                elegible=True,
                motivo_inelegibilidad=None,
            ),
            CandidatoOut(
                posicion=2,
                medico=_CARLOS,
                postulado_en=_instante(16, 20, 30),
                coberturas_mes=1,
                horas_semana=0.0,
                elegible=True,
                motivo_inelegibilidad=None,
            ),
            CandidatoOut(
                posicion=None,
                medico=PersonaOut(id=4, nombre="Ana Soto"),
                postulado_en=_instante(16, 20, 10),
                coberturas_mes=0,
                horas_semana=24.0,
                elegible=False,
                motivo_inelegibilidad=Motivo.GUARDIA_SUPERPUESTA,
            ),
        ],
    ),
    "AsignacionOut": AsignacionOut(
        turno_id=_TURNO,
        asignado=_MARIANO,
        caso=CasoAsignacion.CANDIDATO_ELEGIDO,
        vacante=_VACANTE_ABIERTA.model_copy(update={"estado": EstadoVacante.CUBIERTA, "cerrada_en": _instante(17, 1)}),
    ),
}

# El OpenAPI de /docs muestra estos ejemplos en las respuestas.
for _nombre, _ejemplo in EJEMPLOS.items():
    _clase = type(_ejemplo)
    _clase.model_config["json_schema_extra"] = {"examples": [_ejemplo.model_dump(by_alias=True, mode="json")]}
    _clase.model_rebuild(force=True)

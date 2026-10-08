import pytest
from pydantic import ValidationError

from app.api import esquemas_operacion as esq
from app.api.esquemas_operacion import EJEMPLOS


@pytest.mark.parametrize("nombre", sorted(EJEMPLOS))
def test_cada_ejemplo_valida_contra_su_esquema(nombre):
    clase = getattr(esq, nombre)
    ejemplo = EJEMPLOS[nombre]
    assert isinstance(ejemplo, clase)
    assert clase.model_validate(ejemplo.model_dump(by_alias=True, mode="json")) == ejemplo


def test_hay_un_ejemplo_por_cada_respuesta_del_contrato():
    assert set(EJEMPLOS) == {
        "VacanteOut",
        "LoteVacantesOut",
        "PostulacionOut",
        "CandidatosOut",
        "AsignacionOut",
    }


def test_los_ejemplos_salen_en_camel_case():
    json = EJEMPLOS["VacanteOut"].model_dump_json(by_alias=True)
    assert '"turnoId"' in json and '"generadaPor"' in json and '"creadaEn"' in json


def test_instantes_de_ejemplo_llevan_desplazamiento():
    assert "-03:00" in EJEMPLOS["VacanteOut"].model_dump_json(by_alias=True)


def test_el_ejemplo_de_candidatos_incluye_un_no_elegible_sin_posicion():
    candidatos = EJEMPLOS["CandidatosOut"].candidatos
    assert [c.posicion for c in candidatos if c.elegible] == [1, 2]
    assert [c.posicion for c in candidatos if not c.elegible] == [None]
    assert all(c.motivo_inelegibilidad is not None for c in candidatos if not c.elegible)


def test_lote_rechaza_lista_vacia_y_mas_de_31():
    with pytest.raises(ValidationError):
        esq.LoteVacantesIn(turno_ids=[])
    with pytest.raises(ValidationError):
        esq.LoteVacantesIn(turno_ids=[f"7:2026-10-{d:02d}" for d in range(1, 32)] + ["7:2026-11-01"])
    assert len(esq.LoteVacantesIn(turno_ids=["7:2026-10-17"]).turno_ids) == 1


def test_asignar_acepta_camel_case_y_reasignar_es_falso_por_defecto():
    datos = esq.AsignarIn.model_validate({"medicoId": 3})
    assert datos.medico_id == 3 and datos.reasignar is False


# --- rutas con respuestas de ejemplo (sin base de datos) ---

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import get_verificador, usuario_actual  # noqa: E402
from app.db import get_db  # noqa: E402
from app.main import crear_app  # noqa: E402
from app.modelos import EstadoUsuario, RolUsuario, Usuario  # noqa: E402

TURNO = "7:2026-10-17"
RUTAS_DEL_CONTRATO = [
    # método, ruta, cuerpo, status, esquema de respuesta, solo coordinador
    ("POST", f"/api/turnos/{TURNO}/vacantes", {"motivo": "Congreso"}, 201, "VacanteOut", False),
    ("POST", "/api/vacantes/lote", {"turnoIds": [TURNO], "motivo": "Vacaciones"}, 201, "LoteVacantesOut", True),
    ("POST", "/api/vacantes/12/retiro", None, 200, "VacanteOut", False),
    ("POST", f"/api/turnos/{TURNO}/postulaciones", None, 201, "PostulacionOut", False),
    ("POST", "/api/postulaciones/31/retiro", None, 200, "PostulacionOut", False),
    ("GET", f"/api/turnos/{TURNO}/candidatos", None, 200, "CandidatosOut", True),
    ("PUT", f"/api/turnos/{TURNO}/asignacion", {"medicoId": 2}, 200, "AsignacionOut", True),
]
# Etapa 2: generar vacante, lote y retiro ya son reales (tests/test_api_vacantes.py).
RUTAS = [r for r in RUTAS_DEL_CONTRATO if "vacantes" not in r[1]]
IDS = [f"{m} {r}" for m, r, *_ in RUTAS]


def _usuario(rol: RolUsuario) -> Usuario:
    return Usuario(id=99, nombre="Prueba", email="prueba@prueba.test", rol=rol, estado=EstadoUsuario.ACTIVO)


def _cliente(rol: RolUsuario | None) -> TestClient:
    app = crear_app()
    app.dependency_overrides[get_verificador] = lambda: object()  # sin Supabase configurado
    app.dependency_overrides[get_db] = _base_prohibida
    if rol is not None:
        app.dependency_overrides[usuario_actual] = lambda: _usuario(rol)
    return TestClient(app)


def _base_prohibida():
    raise AssertionError("las rutas de ejemplo no deben tocar la base de datos")


def _pedir(cliente: TestClient, metodo: str, ruta: str, cuerpo):
    return cliente.request(metodo, ruta, json=cuerpo)


def test_las_siete_rutas_estan_en_el_openapi():
    rutas = _cliente(None).get("/openapi.json").json()["paths"]
    for metodo, ruta, *_ in RUTAS_DEL_CONTRATO:
        patron = ruta.replace(TURNO, "{turno_id}").replace("/12/", "/{vacante_id}/").replace("/31/", "/{postulacion_id}/")
        assert metodo.lower() in rutas[patron], (metodo, patron)


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo", "_s", "_e", "_c"), RUTAS, ids=IDS)
def test_sin_token_responde_401(metodo, ruta, cuerpo, _s, _e, _c):
    respuesta = _pedir(_cliente(None), metodo, ruta, cuerpo)
    assert respuesta.status_code == 401
    assert respuesta.json()["codigo"] == "SIN_SESION"


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo", "_s", "_e", "solo_coordinador"), RUTAS, ids=IDS)
def test_las_rutas_de_coordinacion_rechazan_a_un_medico(metodo, ruta, cuerpo, _s, _e, solo_coordinador):
    respuesta = _pedir(_cliente(RolUsuario.MEDICO), metodo, ruta, cuerpo)
    if solo_coordinador:
        assert respuesta.status_code == 403 and respuesta.json()["codigo"] == "SIN_PERMISO"
    else:
        assert respuesta.status_code != 403


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo", "status", "esquema", "_c"), RUTAS, ids=IDS)
def test_la_respuesta_de_ejemplo_valida_y_lleva_el_encabezado(metodo, ruta, cuerpo, status, esquema, _c):
    respuesta = _pedir(_cliente(RolUsuario.COORDINADOR), metodo, ruta, cuerpo)
    assert respuesta.status_code == status
    assert respuesta.headers["X-Respuesta-Ejemplo"] == "true"
    clase = getattr(esq, esquema)
    assert clase.model_validate(respuesta.json()) == EJEMPLOS[esquema]


@pytest.mark.parametrize("ruta", ["/api/turnos/7-2026-10-17/postulaciones", "/api/turnos/7:2026-13-45/candidatos"])
def test_turno_id_mal_formado_responde_422(ruta):
    metodo = "POST" if ruta.endswith("postulaciones") else "GET"
    respuesta = _pedir(_cliente(RolUsuario.COORDINADOR), metodo, ruta, {} if metodo == "POST" else None)
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "TURNO_ID_INVALIDO"

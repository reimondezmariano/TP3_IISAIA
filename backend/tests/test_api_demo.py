from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings, get_settings
from app.main import app
from app.reloj import RelojFijo, get_reloj_sistema
from app.repos.consolidacion import bloquear_marca, desfase_demo, guardar_marca
from fabricas import crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno
from scripts.seed import cargar_datos_ejemplo

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
REAL = datetime(2026, 10, 12, 9, 0, tzinfo=ZONA)


@pytest.fixture
def demo(cliente):
    app.dependency_overrides[get_settings] = lambda: Settings(modo_demo=True)
    app.dependency_overrides[get_reloj_sistema] = lambda: RelojFijo(REAL)
    yield
    app.dependency_overrides.pop(get_settings, None)
    app.dependency_overrides.pop(get_reloj_sistema, None)


def test_adelanta_el_reloj(demo, cliente, sesion, como_coordinador):
    r = cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00-03:00"})
    assert r.status_code == 200
    assert r.json() == {"ahora": "2026-10-15T08:00:00-03:00", "desfaseHoras": 71.0}
    assert desfase_demo(sesion) == timedelta(hours=71)


def test_no_vuelve_hacia_atras(demo, cliente, sesion, como_coordinador):
    # Review Focus 2: un turno ya consolidado quedaría en el futuro.
    cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00-03:00"})
    r = cliente.post("/api/demo/reloj", json={"ahora": "2026-10-13T08:00:00-03:00"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "RELOJ_HACIA_ATRAS"
    assert desfase_demo(sesion) == timedelta(hours=71)


def test_null_vuelve_a_la_hora_real_si_no_hay_historia_adelantada(demo, cliente, sesion, como_coordinador):
    cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00-03:00"})
    r = cliente.post("/api/demo/reloj", json={"ahora": None})
    assert r.json() == {"ahora": "2026-10-12T09:00:00-03:00", "desfaseHoras": 0.0}
    assert desfase_demo(sesion) == timedelta(0)


def test_null_con_la_marca_adelantada_pide_reiniciar_la_demo(demo, cliente, sesion, como_coordinador):
    cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00-03:00"})
    bloquear_marca(sesion)
    guardar_marca(sesion, date(2026, 10, 15))  # se consolidó con el reloj adelantado
    r = cliente.post("/api/demo/reloj", json={"ahora": None})
    assert r.status_code == 409
    assert r.json()["codigo"] == "REINICIAR_DEMO"
    assert desfase_demo(sesion) == timedelta(hours=71)


def test_null_con_un_turno_consolidado_en_el_futuro_pide_reiniciar_la_demo(demo, cliente, sesion, como_coordinador):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id)
    guardar_turno(sesion, horario.id, date(2026, 10, 13), consolidado_en=datetime(2026, 10, 14, tzinfo=ZONA))
    cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00-03:00"})
    r = cliente.post("/api/demo/reloj", json={"ahora": None})
    assert r.status_code == 409
    assert r.json()["codigo"] == "REINICIAR_DEMO"


def test_el_seed_vuelve_a_la_hora_real(demo, cliente, sesion, como_coordinador):
    cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00-03:00"})
    cargar_datos_ejemplo(sesion)
    assert desfase_demo(sesion) == timedelta(0)


def test_instante_sin_zona_es_error_de_validacion(demo, cliente, como_coordinador):
    r = cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDACION"


def test_un_medico_no_mueve_el_reloj(demo, cliente, sesion, reloj):
    cliente.headers.update(encabezados(crear_usuario(sesion, "Ana")))
    r = cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00-03:00"})
    assert r.status_code == 403
    assert desfase_demo(sesion) == timedelta(0)


def test_fuera_de_modo_demo_no_existe(cliente, sesion, como_coordinador):
    app.dependency_overrides[get_settings] = lambda: Settings(modo_demo=False)
    try:
        r = cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00-03:00"})
    finally:
        app.dependency_overrides.pop(get_settings, None)
    assert r.status_code == 404
    assert r.json()["codigo"] == "NO_ENCONTRADO"
    assert desfase_demo(sesion) == timedelta(0)

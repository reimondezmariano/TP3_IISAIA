"""El servidor entrega la compilación del frontend en un solo servicio (D05). No necesitan Postgres."""

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import crear_app

INDEX = "<!doctype html><h1>Guardia Viva</h1>"


class BaseFalsa:
    def execute(self, *_args, **_kwargs):
        return None


@pytest.fixture
def carpeta(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX, encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('hola')", encoding="utf-8")
    (tmp_path / "secreto.txt").write_text("CONTENIDO-SECRETO", encoding="utf-8")
    return dist


def cliente_de(carpeta) -> TestClient:
    app = crear_app(carpeta)
    app.dependency_overrides[get_db] = lambda: BaseFalsa()
    return TestClient(app)


def test_la_raiz_sirve_el_index(carpeta):
    r = cliente_de(carpeta).get("/")
    assert r.status_code == 200
    assert "Guardia Viva" in r.text and r.headers["content-type"].startswith("text/html")


def test_sirve_un_archivo_de_assets_con_su_tipo(carpeta):
    r = cliente_de(carpeta).get("/assets/app.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"] and "hola" in r.text


def test_api_health_sigue_respondiendo_json(carpeta):
    r = cliente_de(carpeta).get("/api/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


def test_una_ruta_de_api_inexistente_responde_404_y_no_el_index(carpeta):
    r = cliente_de(carpeta).get("/api/no-existe")
    assert r.status_code == 404
    assert "Guardia Viva" not in r.text
    assert r.json()["codigo"] == "NO_ENCONTRADO"


@pytest.mark.parametrize(
    "ruta",
    ["/..%2Fsecreto.txt", "/assets/..%2F..%2Fsecreto.txt", "/%2e%2e/secreto.txt", "/assets/../../secreto.txt"],
)
def test_no_sirve_archivos_fuera_de_la_carpeta(carpeta, ruta):
    r = cliente_de(carpeta).get(ruta)
    assert "CONTENIDO-SECRETO" not in r.text


def test_sin_carpeta_la_app_arranca_y_la_raiz_responde_404(tmp_path):
    app = crear_app(tmp_path / "no-existe")
    app.dependency_overrides[get_db] = lambda: BaseFalsa()
    cliente = TestClient(app)
    assert cliente.get("/").status_code == 404
    assert cliente.get("/api/health").status_code == 200


def test_por_defecto_busca_frontend_dist_en_la_raiz_del_repo():
    from pathlib import Path

    from app import main

    assert main.CARPETA_FRONTEND == Path(main.__file__).resolve().parents[2] / "frontend" / "dist"

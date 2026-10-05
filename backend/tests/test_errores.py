from fastapi.testclient import TestClient

from app.errores import ErrorDominio
from app.main import crear_app


def _cliente_con_ruta_de_prueba() -> TestClient:
    app = crear_app()

    @app.get("/api/prueba/error")
    def _falla():
        raise ErrorDominio("ALGO_INVALIDO", "Algo no se puede", 409)

    @app.get("/api/prueba/numero")
    def _numero(n: int):
        return {"n": n}

    return TestClient(app)


def test_error_dominio_tiene_status_422_por_defecto():
    assert ErrorDominio("X", "y").status == 422


def test_error_dominio_se_responde_con_formato_unico():
    r = _cliente_con_ruta_de_prueba().get("/api/prueba/error")
    assert r.status_code == 409
    assert r.json() == {"codigo": "ALGO_INVALIDO", "mensaje": "Algo no se puede"}


def test_error_de_validacion_se_reescribe_al_formato_unico():
    r = _cliente_con_ruta_de_prueba().get("/api/prueba/numero", params={"n": "abc"})
    assert r.status_code == 422
    cuerpo = r.json()
    assert set(cuerpo) == {"codigo", "mensaje"}
    assert cuerpo["codigo"] == "VALIDACION"
    assert "n" in cuerpo["mensaje"]


def test_ruta_inexistente_responde_404_con_formato_unico():
    r = _cliente_con_ruta_de_prueba().get("/api/no-existe")
    assert r.status_code == 404
    assert r.json()["codigo"] == "NO_ENCONTRADO"

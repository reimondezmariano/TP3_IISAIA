from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.main import app


def test_health_responde_ok_con_la_hora_del_reloj(cliente, reloj):
    r = cliente.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok", "base": "ok", "ahora": "2026-10-12T09:00:00-03:00"}


class _SesionCaida:
    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("conexión rechazada"))


def test_health_sin_base_responde_503():
    app.dependency_overrides[get_db] = lambda: _SesionCaida()
    try:
        with TestClient(app) as c:
            r = c.get("/api/health")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 503
    assert r.json()["codigo"] == "BASE_NO_DISPONIBLE"

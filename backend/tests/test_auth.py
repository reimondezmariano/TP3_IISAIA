import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.manejadores import registrar_manejadores
from app.auth import Identidad, VerificadorToken, _cliente_jwks, get_verificador, identidad_actual
from app.config import get_settings
from app.errores import ErrorDominio
from fabricas import SECRETO_PRUEBA, token_para

AUTH_ID = uuid.UUID("2b6f0c1e-8a54-4a43-9a51-6f1c1f0d9e11")
CLAVE_EC = ec.generate_private_key(ec.SECP256R1())


class ClavesFijas:
    """Reemplaza al cliente JWKS de Supabase: siempre devuelve la misma clave pública."""

    def __init__(self, clave_publica) -> None:
        self._clave = clave_publica

    def get_signing_key_from_jwt(self, _token: str):
        return SimpleNamespace(key=self._clave)


def con_secreto() -> VerificadorToken:
    return VerificadorToken(secreto=SECRETO_PRUEBA)


def con_jwks() -> VerificadorToken:
    return VerificadorToken(jwks=ClavesFijas(CLAVE_EC.public_key()))


def error_de(verificador: VerificadorToken, token: str) -> ErrorDominio:
    with pytest.raises(ErrorDominio) as excinfo:
        verificador.verificar(token)
    return excinfo.value


def test_token_hs256_valido_devuelve_la_identidad():
    identidad = con_secreto().verificar(token_para(AUTH_ID, email="florencia@prueba.test"))
    assert identidad == Identidad(auth_id=AUTH_ID, email="florencia@prueba.test")


def test_token_es256_se_verifica_con_la_clave_publica():
    token = token_para(AUTH_ID, clave=CLAVE_EC, algoritmo="ES256")
    assert con_jwks().verificar(token).auth_id == AUTH_ID


def test_token_sin_email_da_identidad_sin_email():
    assert con_secreto().verificar(token_para(AUTH_ID, email=None)).email is None


def test_token_vencido():
    error = error_de(con_secreto(), token_para(AUTH_ID, vence_en=timedelta(seconds=-30)))
    assert (error.codigo, error.status) == ("TOKEN_VENCIDO", 401)


@pytest.mark.parametrize(
    "token",
    [
        "no-es-un-jwt",
        token_para(AUTH_ID, clave="otro-secreto-que-tambien-tiene-32-bytes-o-mas"),
        token_para(AUTH_ID, clave=None, algoritmo="none"),
        token_para(AUTH_ID, aud="otra-audiencia"),
        token_para(AUTH_ID, aud=None),
        token_para(AUTH_ID, sub=None),
        token_para(AUTH_ID, sub="no-es-un-uuid"),
        token_para(AUTH_ID, exp=None),
        token_para(AUTH_ID, clave=CLAVE_EC, algoritmo="ES256"),
    ],
    ids=["basura", "otra-clave", "sin-firma", "otra-audiencia", "sin-audiencia", "sin-sub", "sub-no-uuid", "sin-exp", "es256-sin-jwks"],
)
def test_tokens_invalidos(token):
    error = error_de(con_secreto(), token)
    assert (error.codigo, error.status) == ("TOKEN_INVALIDO", 401)


def test_token_hs256_con_verificador_solo_jwks_es_invalido():
    error = error_de(con_jwks(), token_para(AUTH_ID))
    assert error.codigo == "TOKEN_INVALIDO"


def test_sin_configuracion_de_supabase_responde_503(monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_url", "")
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", "")
    with pytest.raises(ErrorDominio) as excinfo:
        get_verificador()
    assert (excinfo.value.codigo, excinfo.value.status) == ("AUTH_NO_CONFIGURADA", 503)


def test_las_claves_publicas_salen_de_la_url_del_proyecto():
    assert _cliente_jwks("https://abc.supabase.co/").uri == "https://abc.supabase.co/auth/v1/.well-known/jwks.json"


@pytest.fixture
def cliente_identidad() -> TestClient:
    app = FastAPI()
    registrar_manejadores(app)

    @app.get("/quien")
    def quien(identidad: Identidad = Depends(identidad_actual)) -> dict[str, str]:
        return {"authId": str(identidad.auth_id)}

    app.dependency_overrides[get_verificador] = con_secreto
    return TestClient(app)


def test_bearer_valido_llega_al_endpoint(cliente_identidad):
    r = cliente_identidad.get("/quien", headers={"Authorization": f"Bearer {token_para(AUTH_ID)}"})
    assert r.status_code == 200
    assert r.json() == {"authId": str(AUTH_ID)}


@pytest.mark.parametrize("encabezados", [{}, {"Authorization": "Basic dXN1YXJpbzpjbGF2ZQ=="}, {"Authorization": "Bearer"}])
def test_sin_bearer_es_sin_sesion(cliente_identidad, encabezados):
    r = cliente_identidad.get("/quien", headers=encabezados)
    assert r.status_code == 401
    assert r.json()["codigo"] == "SIN_SESION"


def test_bearer_vencido_responde_token_vencido(cliente_identidad):
    token = token_para(AUTH_ID, vence_en=timedelta(seconds=-30))
    r = cliente_identidad.get("/quien", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json() == {"codigo": "TOKEN_VENCIDO", "mensaje": "La sesión venció. Volvé a ingresar."}

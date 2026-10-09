import uuid

import pytest
from sqlalchemy import func, select, text

from app.config import get_settings
from app.modelos import EstadoUsuario, Notificacion, RolUsuario, Usuario
from fabricas import crear_usuario, token_para

CODIGO = "SMG"


@pytest.fixture(autouse=True)
def codigo_configurado(monkeypatch):
    monkeypatch.setattr(get_settings(), "codigo_coordinacion", CODIGO)


def registrar(cliente, auth_id, email="ana@prueba.test", **cuerpo):
    datos = {"nombre": "Ana Pérez", **cuerpo}
    token = token_para(auth_id, email=email)
    return cliente.post("/api/registro", json=datos, headers={"Authorization": f"Bearer {token}"})


def usuarios_con_cuenta(sesion, auth_id) -> int:
    return sesion.scalar(select(func.count()).select_from(Usuario).where(Usuario.auth_id == auth_id))


def test_sin_codigo_queda_medico_pendiente(cliente, sesion):
    auth_id = uuid.uuid4()

    r = registrar(cliente, auth_id)

    assert r.status_code == 201
    cuerpo = r.json()
    assert {k: cuerpo[k] for k in ("nombre", "email", "rol", "estado")} == {
        "nombre": "Ana Pérez",
        "email": "ana@prueba.test",
        "rol": "MEDICO",
        "estado": "PENDIENTE",
    }
    usuario = sesion.scalar(select(Usuario).where(Usuario.auth_id == auth_id))
    assert usuario.id == cuerpo["id"]


def test_con_codigo_correcto_queda_coordinador_activo(cliente):
    r = registrar(cliente, uuid.uuid4(), codigoCoordinacion=" smg ")

    assert r.status_code == 201
    assert (r.json()["rol"], r.json()["estado"]) == ("COORDINADOR", "ACTIVO")


def test_codigo_incorrecto_es_422_y_no_crea_nada(cliente, sesion):
    auth_id = uuid.uuid4()

    r = registrar(cliente, auth_id, codigoCoordinacion="ABC")

    assert r.status_code == 422
    assert r.json()["codigo"] == "CODIGO_INVALIDO"
    assert usuarios_con_cuenta(sesion, auth_id) == 0


def test_codigo_en_blanco_cuenta_como_sin_codigo(cliente):
    r = registrar(cliente, uuid.uuid4(), codigoCoordinacion="   ")

    assert r.status_code == 201
    assert r.json()["rol"] == "MEDICO"


def test_sin_codigo_configurado_nadie_es_coordinador(cliente, monkeypatch):
    monkeypatch.setattr(get_settings(), "codigo_coordinacion", "")

    r = registrar(cliente, uuid.uuid4(), codigoCoordinacion="SMG")

    assert r.status_code == 422
    assert r.json()["codigo"] == "CODIGO_INVALIDO"


@pytest.mark.parametrize("nombre", ["", "   "])
def test_nombre_vacio_es_error_de_validacion(cliente, nombre):
    r = registrar(cliente, uuid.uuid4(), nombre=nombre)

    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDACION"


def test_email_cargado_vincula_la_cuenta_y_conserva_el_rol(cliente, sesion):
    enzo = crear_usuario(
        sesion, "Enzo", rol=RolUsuario.COORDINADOR, email="Enzo@GuardiaViva.test", con_cuenta=False
    )
    auth_id = uuid.uuid4()

    r = registrar(cliente, auth_id, email="enzo@guardiaviva.test", nombre="Otro nombre", codigoCoordinacion=CODIGO)

    assert r.status_code == 200
    assert r.json() == {
        "id": enzo.id,
        "nombre": "Enzo",
        "email": "Enzo@GuardiaViva.test",
        "rol": "COORDINADOR",
        "estado": "ACTIVO",
    }
    sesion.refresh(enzo)
    assert enzo.auth_id == auth_id


def test_vincular_no_cambia_el_rol_aunque_traiga_el_codigo(cliente, sesion):
    medico = crear_usuario(sesion, "Carlos Lugones", email="carlos@prueba.test", con_cuenta=False)

    r = registrar(cliente, uuid.uuid4(), email="carlos@prueba.test", codigoCoordinacion=CODIGO)

    assert r.status_code == 200
    assert (r.json()["id"], r.json()["rol"]) == (medico.id, "MEDICO")


def test_registrarse_dos_veces_es_409(cliente):
    auth_id = uuid.uuid4()
    assert registrar(cliente, auth_id).status_code == 201

    r = registrar(cliente, auth_id)

    assert r.status_code == 409
    assert r.json()["codigo"] == "YA_REGISTRADO"


def test_email_de_otra_cuenta_es_409(cliente, sesion):
    crear_usuario(sesion, "Ana Pérez", email="ana@prueba.test")

    r = registrar(cliente, uuid.uuid4(), email="ana@prueba.test")

    assert r.status_code == 409
    assert r.json()["codigo"] == "EMAIL_YA_REGISTRADO"


def test_cuenta_vinculada_con_otro_email_choca_con_la_restriccion_de_la_base(cliente, sesion):
    """Regla 8: el duplicado de cuenta lo detecta la restricción única de auth_id, no una consulta previa."""
    ana = crear_usuario(sesion, "Ana Pérez", email="ana@prueba.test")
    # El endpoint hace rollback al chocar: sin este commit (que en la sesión de pruebas libera el
    # savepoint, sin confirmar la transacción externa), el rollback se llevaría también a Ana.
    sesion.commit()

    r = registrar(cliente, ana.auth_id, email="ana.nueva@prueba.test")

    assert r.status_code == 409
    assert r.json()["codigo"] == "YA_REGISTRADO"
    assert usuarios_con_cuenta(sesion, ana.auth_id) == 1


def test_token_sin_email_es_403(cliente):
    """El token es válido: con 401 la interfaz renovaría la sesión en un bucle sin resolver nada."""
    r = registrar(cliente, uuid.uuid4(), email=None)

    assert r.status_code == 403
    assert r.json()["codigo"] == "TOKEN_SIN_EMAIL"


def test_registro_sin_token_es_401(cliente):
    r = cliente.post("/api/registro", json={"nombre": "Ana Pérez"})

    assert r.status_code == 401
    assert r.json()["codigo"] == "SIN_SESION"


def test_despues_del_registro_me_responde_pendiente(cliente):
    auth_id = uuid.uuid4()
    registrar(cliente, auth_id)

    r = cliente.get("/api/me", headers={"Authorization": f"Bearer {token_para(auth_id, email='ana@prueba.test')}"})

    assert r.status_code == 200
    assert r.json()["estado"] == EstadoUsuario.PENDIENTE.value


def test_vincular_un_email_que_otra_cuenta_vinculo_recien_es_409(cliente, sesion):
    """Regla 8: entre la búsqueda y el UPDATE, otro registro vinculó el email. Gana el primero; el segundo, 409."""
    carlos = crear_usuario(sesion, "Carlos Lugones", email="carlos@prueba.test", con_cuenta=False)
    primera = uuid.uuid4()
    # La otra vinculación llega a la base sin pasar por el objeto ya cargado (que sigue viendo auth_id vacío).
    sesion.execute(text("UPDATE usuario SET auth_id = :a WHERE id = :id"), {"a": primera, "id": carlos.id})

    r = registrar(cliente, uuid.uuid4(), email="carlos@prueba.test")

    assert r.status_code == 409
    assert r.json()["codigo"] == "EMAIL_YA_REGISTRADO"
    assert sesion.scalar(text("SELECT auth_id FROM usuario WHERE id = :id"), {"id": carlos.id}) == primera


@pytest.mark.parametrize("codigo", [None, "   "])
def test_vincular_un_coordinador_cargado_exige_el_codigo(cliente, sesion, codigo):
    """Sin confirmación de email (D06), cualquiera puede crear en Supabase la cuenta de un email cargado."""
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR, email="enzo@guardiaviva.test", con_cuenta=False)

    r = registrar(cliente, uuid.uuid4(), email="enzo@guardiaviva.test", codigoCoordinacion=codigo)

    assert r.status_code == 422
    assert r.json()["codigo"] == "CODIGO_REQUERIDO"
    sesion.refresh(enzo)
    assert enzo.auth_id is None


def test_vincular_un_coordinador_cargado_con_codigo_incorrecto_es_422(cliente, sesion):
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR, email="enzo@guardiaviva.test", con_cuenta=False)

    r = registrar(cliente, uuid.uuid4(), email="enzo@guardiaviva.test", codigoCoordinacion="ABC")

    assert r.json()["codigo"] == "CODIGO_INVALIDO"
    sesion.refresh(enzo)
    assert enzo.auth_id is None


def avisos_de_registro(sesion) -> list[Notificacion]:
    return list(
        sesion.scalars(select(Notificacion).where(Notificacion.tipo == "NUEVO_REGISTRO").order_by(Notificacion.usuario_id))
    )


def test_registro_pendiente_avisa_a_los_coordinadores_activos(cliente, sesion, reloj):
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    laura = crear_usuario(sesion, "Laura", rol=RolUsuario.COORDINADOR)
    crear_usuario(sesion, "Coordinadora pendiente", rol=RolUsuario.COORDINADOR, estado=EstadoUsuario.PENDIENTE)
    crear_usuario(sesion, "Médico activo")

    r = registrar(cliente, uuid.uuid4())

    assert r.status_code == 201
    avisos = avisos_de_registro(sesion)
    assert [a.usuario_id for a in avisos] == [enzo.id, laura.id]
    assert {a.mensaje for a in avisos} == {"Ana Pérez se registró y espera activación"}
    assert {a.creada_en for a in avisos} == {reloj.ahora()}
    assert avisos[0].datos == {"usuario_id": r.json()["id"]}


def test_registro_con_codigo_no_avisa(cliente, sesion):
    crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)

    r = registrar(cliente, uuid.uuid4(), codigoCoordinacion=CODIGO)

    assert r.status_code == 201
    assert avisos_de_registro(sesion) == []


def test_vincular_un_medico_cargado_activo_no_avisa(cliente, sesion):
    crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    crear_usuario(sesion, "Carlos", email="carlos@prueba.test", con_cuenta=False)

    r = registrar(cliente, uuid.uuid4(), email="carlos@prueba.test")

    assert r.status_code == 200
    assert avisos_de_registro(sesion) == []


def test_registro_rechazado_no_avisa(cliente, sesion):
    crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    auth_id = uuid.uuid4()
    registrar(cliente, auth_id)

    r = registrar(cliente, auth_id)

    assert r.status_code == 409
    assert len(avisos_de_registro(sesion)) == 1

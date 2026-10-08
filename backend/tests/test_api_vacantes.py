import pytest
from sqlalchemy import func, select

from app.modelos import EstadoVacante, EventoTurno, RolUsuario, Vacante
from fabricas import crear_horario_de_prueba, crear_usuario, encabezados

# Reloj fijo: lunes 12/10/2026 09:00. El turno del martes 13/10 está a 23 h (urgente); el del 20/10 no.
URGENTE = "2026-10-13"
LEJANO = "2026-10-20"


@pytest.fixture
def escena(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    horario = crear_horario_de_prueba(sesion, carlos.id)  # martes 08:00 a 20:00
    return carlos, enzo, horario


def como(cliente, usuario):
    cliente.headers.clear()
    cliente.headers.update(encabezados(usuario))


def generar(cliente, horario, fecha, motivo=None):
    return cliente.post(f"/api/turnos/{horario.id}:{fecha}/vacantes", json={"motivo": motivo})


def test_generar_responde_201_con_el_formato_del_contrato(cliente, escena):
    carlos, _, horario = escena
    como(cliente, carlos)

    r = generar(cliente, horario, LEJANO, "Congreso")

    assert r.status_code == 201
    assert "X-Respuesta-Ejemplo" not in r.headers
    cuerpo = r.json()
    assert set(cuerpo) == {"id", "turnoId", "estado", "urgente", "motivo", "generadaPor", "creadaEn", "cerradaEn"}
    assert cuerpo["turnoId"] == f"{horario.id}:{LEJANO}"
    assert (cuerpo["estado"], cuerpo["urgente"], cuerpo["cerradaEn"]) == ("ABIERTA", False, None)
    assert cuerpo["generadaPor"] == {"id": carlos.id, "nombre": "Carlos Lugones"}
    assert cuerpo["creadaEn"] == "2026-10-12T09:00:00-03:00"


def test_urgente_se_calcula_en_la_respuesta(cliente, escena):
    carlos, _, horario = escena
    como(cliente, carlos)
    assert generar(cliente, horario, URGENTE).json()["urgente"] is True


def test_el_medico_no_ve_el_motivo_y_el_coordinador_si(cliente, sesion, escena):
    carlos, enzo, horario = escena
    como(cliente, carlos)
    creada = generar(cliente, horario, LEJANO, "Motivo de salud").json()
    assert creada["motivo"] is None  # D25: ni siquiera quien la generó lo ve en la respuesta

    como(cliente, enzo)
    retirada = cliente.post(f"/api/vacantes/{creada['id']}/retiro")
    assert retirada.status_code == 200 and retirada.json()["motivo"] == "Motivo de salud"

    como(cliente, carlos)
    lote_medico = cliente.post("/api/vacantes/lote", json={"turnoIds": [f"{horario.id}:2026-10-27"]})
    assert lote_medico.status_code == 403

    como(cliente, enzo)
    lote = cliente.post("/api/vacantes/lote", json={"turnoIds": [f"{horario.id}:2026-10-27"], "motivo": "Vacaciones"})
    assert lote.json()["vacantes"][0]["motivo"] == "Vacaciones"


def test_generar_por_un_coordinador_muestra_su_propio_motivo(cliente, escena):
    _, enzo, horario = escena
    como(cliente, enzo)
    assert generar(cliente, horario, LEJANO, "Cobertura de congreso").json()["motivo"] == "Cobertura de congreso"


def test_el_lote_genera_varias_vacantes(cliente, escena):
    _, enzo, horario = escena
    como(cliente, enzo)

    r = cliente.post(
        "/api/vacantes/lote", json={"turnoIds": [f"{horario.id}:2026-10-20", f"{horario.id}:2026-10-27"]}
    )

    assert r.status_code == 201
    assert [v["turnoId"] for v in r.json()["vacantes"]] == [f"{horario.id}:2026-10-20", f"{horario.id}:2026-10-27"]


def test_retirar_responde_200_y_deja_la_vacante_retirada(cliente, sesion, escena):
    carlos, _, horario = escena
    como(cliente, carlos)
    creada = generar(cliente, horario, LEJANO).json()

    r = cliente.post(f"/api/vacantes/{creada['id']}/retiro")

    assert r.status_code == 200
    assert (r.json()["estado"], r.json()["cerradaEn"]) == ("RETIRADA", "2026-10-12T09:00:00-03:00")
    assert sesion.get(Vacante, creada["id"]).estado == EstadoVacante.RETIRADA
    assert sesion.scalar(select(func.count()).select_from(EventoTurno)) == 2


@pytest.mark.parametrize(
    ("caso", "status", "codigo"),
    [
        ("inexistente", 404, "TURNO_NO_ENCONTRADO"),
        ("repetida", 409, "VACANTE_YA_ABIERTA"),
        ("tercero", 403, "SIN_PERMISO"),
        ("empezado", 409, "TURNO_YA_EMPEZO"),
        ("mal_formado", 422, "TURNO_ID_INVALIDO"),
    ],
)
def test_errores_con_codigo_y_status(cliente, sesion, reloj, escena, caso, status, codigo):
    carlos, _, horario = escena
    como(cliente, carlos)
    if caso == "inexistente":
        r = generar(cliente, horario, "2026-10-21")  # miércoles
    elif caso == "repetida":
        generar(cliente, horario, LEJANO)
        r = generar(cliente, horario, LEJANO)
    elif caso == "tercero":
        como(cliente, crear_usuario(sesion, "Tercero"))
        r = generar(cliente, horario, LEJANO)
    elif caso == "empezado":
        from datetime import timedelta

        reloj.avanzar(timedelta(days=1))
        r = generar(cliente, horario, URGENTE)
    else:
        r = cliente.post("/api/turnos/xx/vacantes", json={})
    assert (r.status_code, r.json()["codigo"]) == (status, codigo)


def test_retirar_una_vacante_inexistente_responde_404(cliente, escena):
    carlos, _, _ = escena
    como(cliente, carlos)
    r = cliente.post("/api/vacantes/99999/retiro")
    assert (r.status_code, r.json()["codigo"]) == (404, "VACANTE_NO_ENCONTRADA")


def test_un_lote_con_un_turno_inexistente_no_guarda_ninguna(cliente, sesion, escena):
    _, enzo, horario = escena
    como(cliente, enzo)

    r = cliente.post(
        "/api/vacantes/lote", json={"turnoIds": [f"{horario.id}:2026-10-20", f"{horario.id}:2026-10-21"]}
    )

    assert r.status_code == 404
    assert sesion.scalar(select(func.count()).select_from(Vacante)) == 0


@pytest.mark.parametrize(
    ("metodo", "ruta", "cuerpo"),
    [
        ("POST", "/api/turnos/1:2026-10-20/vacantes", {}),
        ("POST", "/api/vacantes/lote", {"turnoIds": ["1:2026-10-20"]}),
        ("POST", "/api/vacantes/1/retiro", None),
    ],
)
def test_sin_token_responde_401(cliente, metodo, ruta, cuerpo):
    cliente.headers.clear()
    assert cliente.request(metodo, ruta, json=cuerpo).status_code == 401


def test_un_lote_con_un_id_mal_formado_responde_422(cliente, escena):
    _, enzo, horario = escena
    como(cliente, enzo)
    r = cliente.post("/api/vacantes/lote", json={"turnoIds": [f"{horario.id}:2026-10-20", "xx"]})
    assert (r.status_code, r.json()["codigo"]) == (422, "TURNO_ID_INVALIDO")

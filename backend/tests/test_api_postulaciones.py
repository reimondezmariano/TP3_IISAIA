from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.modelos import EstadoVacante, Notificacion, RolUsuario, Turno, Vacante
from fabricas import crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno

# Reloj fijo: lunes 12/10/2026 09:00. El turno de prueba es el martes 20/10 (08:00 a 20:00).
FECHA = "2026-10-20"


@pytest.fixture
def escena(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    horario = crear_horario_de_prueba(sesion, carlos.id)
    return carlos, enzo, horario, f"{horario.id}:{FECHA}"


def como(cliente, usuario):
    cliente.headers.clear()
    cliente.headers.update(encabezados(usuario))


def abrir_vacante(cliente, carlos, turno_id, motivo="Congreso"):
    como(cliente, carlos)
    r = cliente.post(f"/api/turnos/{turno_id}/vacantes", json={"motivo": motivo})
    assert r.status_code == 201
    return r.json()


def postularse(cliente, medico, turno_id):
    como(cliente, medico)
    return cliente.post(f"/api/turnos/{turno_id}/postulaciones")


def test_postularse_responde_201_con_el_formato_del_contrato(cliente, sesion, escena):
    carlos, _, _, turno_id = escena
    abrir_vacante(cliente, carlos, turno_id)
    mariano = crear_usuario(sesion, "Mariano Reimondez")

    r = postularse(cliente, mariano, turno_id)

    assert r.status_code == 201
    assert "X-Respuesta-Ejemplo" not in r.headers
    cuerpo = r.json()
    assert set(cuerpo) == {"id", "turnoId", "medico", "creadaEn", "retiradaEn"}
    assert cuerpo["turnoId"] == turno_id
    assert cuerpo["medico"] == {"id": mariano.id, "nombre": "Mariano Reimondez"}
    assert (cuerpo["creadaEn"], cuerpo["retiradaEn"]) == ("2026-10-12T09:00:00-03:00", None)


def test_retirar_la_postulacion_por_su_dueno_y_por_un_coordinador(cliente, sesion, escena):
    carlos, enzo, _, turno_id = escena
    abrir_vacante(cliente, carlos, turno_id)
    mariano, florencia = crear_usuario(sesion, "Mariano"), crear_usuario(sesion, "Florencia")
    propia = postularse(cliente, mariano, turno_id).json()
    ajena = postularse(cliente, florencia, turno_id).json()

    como(cliente, mariano)
    retirada = cliente.post(f"/api/postulaciones/{propia['id']}/retiro")
    como(cliente, enzo)
    por_coordinador = cliente.post(f"/api/postulaciones/{ajena['id']}/retiro")

    assert retirada.status_code == 200 and retirada.json()["retiradaEn"] == "2026-10-12T09:00:00-03:00"
    assert por_coordinador.status_code == 200 and por_coordinador.json()["retiradaEn"] is not None


@pytest.mark.parametrize(
    ("caso", "status", "codigo"),
    [
        ("coordinador", 403, "NO_HABILITADO"),
        ("titular", 422, "ES_TITULAR"),
        ("sin_vacante", 409, "TURNO_SIN_VACANTE"),
        ("repetida", 409, "YA_POSTULADO"),
        ("inexistente", 404, "TURNO_NO_ENCONTRADO"),
        ("mal_formado", 422, "TURNO_ID_INVALIDO"),
        ("empezado", 409, "TURNO_YA_EMPEZO"),
    ],
)
def test_errores_de_postulacion_con_codigo_y_status(cliente, sesion, reloj, escena, caso, status, codigo):
    carlos, enzo, horario, turno_id = escena
    mariano = crear_usuario(sesion, "Mariano")
    if caso != "sin_vacante":
        abrir_vacante(cliente, carlos, turno_id)
    if caso == "coordinador":
        r = postularse(cliente, enzo, turno_id)
    elif caso == "titular":
        r = postularse(cliente, carlos, turno_id)
    elif caso == "repetida":
        postularse(cliente, mariano, turno_id)
        r = postularse(cliente, mariano, turno_id)
    elif caso == "inexistente":
        r = postularse(cliente, mariano, f"{horario.id}:2026-10-21")
    elif caso == "mal_formado":
        r = postularse(cliente, mariano, "xx")
    elif caso == "empezado":
        reloj.avanzar(timedelta(days=8))
        r = postularse(cliente, mariano, turno_id)
    else:
        r = postularse(cliente, mariano, turno_id)
    assert (r.status_code, r.json()["codigo"]) == (status, codigo)


def test_candidatos_ordenados_por_equidad_en_el_formato_del_contrato(cliente, sesion, reloj, escena):
    carlos, enzo, _, turno_id = escena
    abrir_vacante(cliente, carlos, turno_id)
    ana, beto = crear_usuario(sesion, "Ana"), crear_usuario(sesion, "Beto")
    postularse(cliente, ana, turno_id)
    reloj.avanzar(timedelta(minutes=1))
    postularse(cliente, beto, turno_id)
    otro = crear_usuario(sesion, "Titular de miércoles")
    miercoles = crear_horario_de_prueba(sesion, otro.id, dia=3)
    guardar_turno(sesion, miercoles.id, date(2026, 10, 14), asignado_id=ana.id)  # Ana ya cubrió una vez en octubre

    como(cliente, enzo)
    r = cliente.get(f"/api/turnos/{turno_id}/candidatos")

    assert r.status_code == 200 and "X-Respuesta-Ejemplo" not in r.headers
    cuerpo = r.json()
    assert (cuerpo["turnoId"], cuerpo["mes"]) == (turno_id, "2026-10")
    assert [c["medico"]["nombre"] for c in cuerpo["candidatos"]] == ["Beto", "Ana"]
    primero, segundo = cuerpo["candidatos"]
    assert set(primero) == {
        "posicion", "medico", "postuladoEn", "coberturasMes", "horasSemana", "elegible", "motivoInelegibilidad"
    }
    assert (primero["posicion"], primero["coberturasMes"], primero["elegible"]) == (1, 0, True)
    # la cobertura del 14/10 cuenta para octubre pero no para la semana del turno (lunes 19 a domingo 25)
    assert (segundo["posicion"], segundo["coberturasMes"], segundo["horasSemana"]) == (2, 1, 0.0)


def test_un_medico_no_ve_los_candidatos_ni_asigna(cliente, sesion, escena):
    carlos, _, _, turno_id = escena
    como(cliente, carlos)
    assert cliente.get(f"/api/turnos/{turno_id}/candidatos").status_code == 403
    r = cliente.put(f"/api/turnos/{turno_id}/asignacion", json={"medicoId": carlos.id})
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")


def test_el_flujo_completo(cliente, sesion, escena):
    carlos, enzo, _, turno_id = escena
    abrir_vacante(cliente, carlos, turno_id, "Congreso")
    ana, beto = crear_usuario(sesion, "Ana"), crear_usuario(sesion, "Beto")
    postularse(cliente, ana, turno_id)
    postularse(cliente, beto, turno_id)

    como(cliente, enzo)
    candidatos = cliente.get(f"/api/turnos/{turno_id}/candidatos").json()["candidatos"]
    elegido = candidatos[1]["medico"]  # el coordinador no está obligado a elegir al primero
    r = cliente.put(f"/api/turnos/{turno_id}/asignacion", json={"medicoId": elegido["id"]})

    assert r.status_code == 200 and "X-Respuesta-Ejemplo" not in r.headers
    cuerpo = r.json()
    assert (cuerpo["turnoId"], cuerpo["caso"], cuerpo["asignado"]) == (turno_id, "CANDIDATO_ELEGIDO", elegido)
    assert (cuerpo["vacante"]["estado"], cuerpo["vacante"]["motivo"]) == ("CUBIERTA", "Congreso")
    turno = sesion.scalar(select(Turno))
    assert turno.asignado_id == elegido["id"]
    assert sesion.scalar(select(Vacante.estado)) == EstadoVacante.CUBIERTA
    avisos = list(sesion.scalars(select(Notificacion).where(Notificacion.tipo == "TURNO_ASIGNADO")))
    assert [n.usuario_id for n in avisos] == [elegido["id"]]


def test_reasignar_exige_el_indicador(cliente, sesion, escena):
    carlos, enzo, _, turno_id = escena
    abrir_vacante(cliente, carlos, turno_id)
    ana, beto = crear_usuario(sesion, "Ana"), crear_usuario(sesion, "Beto")
    como(cliente, enzo)
    assert cliente.put(f"/api/turnos/{turno_id}/asignacion", json={"medicoId": ana.id}).status_code == 200

    sin = cliente.put(f"/api/turnos/{turno_id}/asignacion", json={"medicoId": beto.id})
    con = cliente.put(f"/api/turnos/{turno_id}/asignacion", json={"medicoId": beto.id, "reasignar": True})

    assert (sin.status_code, sin.json()["codigo"]) == (409, "YA_TIENE_ASIGNADO")
    assert (con.status_code, con.json()["caso"]) == (200, "REASIGNACION")


def test_errores_de_asignacion_con_codigo_y_status(cliente, sesion, escena):
    carlos, enzo, _, turno_id = escena
    abrir_vacante(cliente, carlos, turno_id)
    como(cliente, enzo)
    pedidos = [
        ({"medicoId": 99999}, 404, "USUARIO_NO_ENCONTRADO"),
        ({"medicoId": enzo.id}, 422, "NO_HABILITADO"),
        ({"medicoId": carlos.id}, 422, "ES_TITULAR"),
        ({}, 422, "VALIDACION"),
    ]
    for cuerpo, status, codigo in pedidos:
        r = cliente.put(f"/api/turnos/{turno_id}/asignacion", json=cuerpo)
        assert (r.status_code, r.json()["codigo"]) == (status, codigo), cuerpo


@pytest.mark.parametrize(
    ("metodo", "ruta", "cuerpo"),
    [
        ("POST", "/api/turnos/1:2026-10-20/postulaciones", None),
        ("POST", "/api/postulaciones/1/retiro", None),
        ("GET", "/api/turnos/1:2026-10-20/candidatos", None),
        ("PUT", "/api/turnos/1:2026-10-20/asignacion", {"medicoId": 1}),
    ],
)
def test_sin_token_responde_401(cliente, metodo, ruta, cuerpo):
    cliente.headers.clear()
    assert cliente.request(metodo, ruta, json=cuerpo).status_code == 401


def test_las_siete_rutas_del_contrato_estan_en_el_openapi(cliente):
    rutas = cliente.get("/openapi.json").json()["paths"]
    esperadas = {
        "/api/turnos/{turno_id}/vacantes": "post",
        "/api/vacantes/lote": "post",
        "/api/vacantes/{vacante_id}/retiro": "post",
        "/api/turnos/{turno_id}/postulaciones": "post",
        "/api/postulaciones/{postulacion_id}/retiro": "post",
        "/api/turnos/{turno_id}/candidatos": "get",
        "/api/turnos/{turno_id}/asignacion": "put",
    }
    for ruta, metodo in esperadas.items():
        assert metodo in rutas[ruta], (metodo, ruta)

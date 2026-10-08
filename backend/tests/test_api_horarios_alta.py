from datetime import date

import pytest

from app.modelos import EstadoUsuario, RolUsuario
from fabricas import crear_usuario, encabezados


def cuerpo(medico_id, **cambios) -> dict:
    base = {
        "medicoId": medico_id,
        "diaSemana": 6,
        "horaInicio": "08:00",
        "duracionHoras": 12,
        "frecuenciaSemanas": 1,
        "fechaAncla": "2026-10-12",
        "vigenteDesde": "2026-10-17",
    }
    base.update(cambios)
    return base


def test_alta_de_horario_formato_exacto_y_aparece_en_el_calendario(cliente, sesion, como_coordinador):
    florencia = crear_usuario(sesion, "Florencia Lucca")

    r = cliente.post("/api/horarios", json=cuerpo(florencia.id))

    assert r.status_code == 201
    datos = r.json()
    assert datos == {
        "id": datos["id"],
        "estado": "CON_TITULAR",
        "versiones": [
            {
                "id": datos["versiones"][0]["id"],
                "medico": {"id": florencia.id, "nombre": "Florencia Lucca"},
                "diaSemana": 6,
                "horaInicio": "08:00:00",
                "duracionHoras": 12,
                "frecuenciaSemanas": 1,
                "fechaAncla": "2026-10-12",
                "vigenteDesde": "2026-10-17",
                "vigenteHasta": None,
            }
        ],
    }
    turnos = cliente.get("/api/turnos", params={"desde": "2026-10-17", "hasta": "2026-10-17"}).json()
    assert [t["id"] for t in turnos] == [f"{datos['id']}:2026-10-17"]


def test_sin_fecha_ancla_usa_el_lunes_de_la_semana_de_inicio(cliente, sesion, como_coordinador):
    florencia = crear_usuario(sesion, "Florencia Lucca")
    datos = cuerpo(florencia.id)
    del datos["fechaAncla"]
    r = cliente.post("/api/horarios", json=datos)
    assert r.status_code == 201
    assert r.json()["versiones"][0]["fechaAncla"] == "2026-10-12"


def test_fecha_ancla_que_no_es_lunes(cliente, sesion, como_coordinador):
    florencia = crear_usuario(sesion, "Florencia Lucca")
    r = cliente.post("/api/horarios", json=cuerpo(florencia.id, fechaAncla="2026-10-13"))
    assert r.status_code == 422
    assert r.json()["codigo"] == "FECHA_ANCLA_NO_LUNES"


def test_alta_con_inicio_en_el_pasado(cliente, sesion, como_coordinador):
    florencia = crear_usuario(sesion, "Florencia Lucca")
    r = cliente.post("/api/horarios", json=cuerpo(florencia.id, vigenteDesde="2026-10-11"))
    assert r.status_code == 422
    assert r.json()["codigo"] == "FECHA_PASADA"


@pytest.mark.parametrize(
    "rol,estado",
    [
        (RolUsuario.COORDINADOR, EstadoUsuario.ACTIVO),
        (RolUsuario.MEDICO, EstadoUsuario.PENDIENTE),
        (RolUsuario.MEDICO, EstadoUsuario.BAJA),
    ],
)
def test_titular_que_no_es_medico_activo(cliente, sesion, como_coordinador, rol, estado):
    otro = crear_usuario(sesion, "No elegible", rol=rol, estado=estado)
    r = cliente.post("/api/horarios", json=cuerpo(otro.id))
    assert r.status_code == 422
    assert r.json()["codigo"] == "TITULAR_INVALIDO"


def test_titular_inexistente(cliente, como_coordinador):
    r = cliente.post("/api/horarios", json=cuerpo(999999))
    assert r.status_code == 422
    assert r.json()["codigo"] == "TITULAR_INVALIDO"


@pytest.mark.parametrize("cambio", [{"duracionHoras": 25}, {"diaSemana": 8}, {"medicoId": None}, {"frecuenciaSemanas": 0}])
def test_datos_fuera_de_rango_son_validacion(cliente, sesion, como_coordinador, cambio):
    florencia = crear_usuario(sesion, "Florencia Lucca")
    r = cliente.post("/api/horarios", json=cuerpo(florencia.id, **cambio))
    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDACION"


def test_un_medico_no_carga_horarios(cliente, sesion, reloj):
    medico = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.post("/api/horarios", json=cuerpo(medico.id), headers=encabezados(medico))
    assert r.status_code == 403
    assert r.json()["codigo"] == "SIN_PERMISO"

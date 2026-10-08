from datetime import date, datetime, time

from app.repos.horarios import DatosVersion, nueva_version
from fabricas import ZONA, crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno


def versiones(cliente, horario_id) -> list[dict]:
    [horario] = [h for h in cliente.get("/api/horarios").json() if h["id"] == horario_id]
    return horario["versiones"]


def test_cambio_de_hora_parte_la_version_y_el_calendario_lo_refleja(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)  # martes 08:00, 12 h

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"})

    assert r.status_code == 201
    version = r.json()["version"]
    assert version["horaInicio"] == "09:00:00"
    assert version["medico"] == {"id": carlos.id, "nombre": "Carlos Lugones"}  # lo omitido se copia
    assert (version["vigenteDesde"], version["vigenteHasta"]) == ("2026-10-20", None)
    assert r.json()["turnosAfectados"] == []
    assert [(v["vigenteDesde"], v["vigenteHasta"]) for v in versiones(cliente, h.id)] == [
        ("2026-09-07", "2026-10-20"),
        ("2026-10-20", None),
    ]
    turnos = cliente.get("/api/turnos", params={"desde": "2026-10-13", "hasta": "2026-10-20"}).json()
    assert [t["inicio"] for t in turnos] == ["2026-10-13T08:00:00-03:00", "2026-10-20T09:00:00-03:00"]


def test_turnos_ya_guardados_conservan_su_foto_y_se_informan(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    paula = crear_usuario(sesion, "Paula Méndez")
    h = crear_horario_de_prueba(sesion, carlos.id)
    guardar_turno(sesion, h.id, date(2026, 10, 13))  # anterior al cambio: no es afectado
    guardar_turno(sesion, h.id, date(2026, 10, 20), asignado_id=paula.id)

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"})

    assert r.json()["turnosAfectados"] == [
        {
            "id": f"{h.id}:2026-10-20",
            "horarioId": h.id,
            "fecha": "2026-10-20",
            "inicio": "2026-10-20T08:00:00-03:00",  # la foto no se recalcula (D11, D12)
            "fin": "2026-10-20T20:00:00-03:00",
            "titular": {"id": carlos.id, "nombre": "Carlos Lugones"},
            "asignado": {"id": paula.id, "nombre": "Paula Méndez"},
        }
    ]


def test_turno_consolidado_hoy_no_es_afectado(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id, dia=1, hora=time(0), dur=6)  # lunes 00:00 a 06:00
    guardar_turno(sesion, h.id, date(2026, 10, 12), consolidado_en=datetime(2026, 10, 12, 7, tzinfo=ZONA))

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-12", "horaInicio": "01:00"})

    assert r.status_code == 201
    assert r.json()["turnosAfectados"] == []


def test_designar_titular_en_un_horario_sin_titular(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, None)
    diego = crear_usuario(sesion, "Diego Sosa")

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-12", "medicoId": diego.id})

    assert r.status_code == 201
    assert r.json()["version"]["medico"] == {"id": diego.id, "nombre": "Diego Sosa"}
    [horario] = [x for x in cliente.get("/api/horarios").json() if x["id"] == h.id]
    assert horario["estado"] == "CON_TITULAR"
    [turno] = cliente.get("/api/turnos", params={"desde": "2026-10-13", "hasta": "2026-10-13"}).json()
    assert turno["titular"] == {"id": diego.id, "nombre": "Diego Sosa"}


def test_medico_id_null_deja_el_horario_sin_titular(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "medicoId": None})

    assert r.status_code == 201
    assert r.json()["version"]["medico"] is None
    [turno] = cliente.get("/api/turnos", params={"desde": "2026-10-20", "hasta": "2026-10-20"}).json()
    assert turno["titular"] is None


def test_cambio_antes_de_una_renegociacion_programada_rige_solo_hasta_ella(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)
    programada = DatosVersion(
        medico_id=carlos.id, dia_semana=2, hora_inicio=time(10), duracion_horas=12,
        frecuencia_semanas=1, fecha_ancla=date(2026, 9, 7),
    )
    nueva_version(sesion, h.id, programada, date(2026, 11, 3))

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"})

    assert r.json()["version"]["vigenteHasta"] == "2026-11-03"
    assert [v["horaInicio"] for v in versiones(cliente, h.id)] == ["08:00:00", "09:00:00", "10:00:00"]


def test_cambio_en_el_pasado(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-11", "horaInicio": "09:00"})
    assert (r.status_code, r.json()["codigo"]) == (422, "FECHA_PASADA")


def test_version_que_empieza_hoy_ya_rige_y_no_se_modifica_en_el_lugar(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id, desde=date(2026, 10, 12))
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-12", "horaInicio": "09:00"})
    assert (r.status_code, r.json()["codigo"]) == (409, "VERSION_EN_ESA_FECHA")


def test_version_que_todavia_no_rige_se_modifica_en_el_lugar(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id, desde=date(2026, 10, 20))
    [antes] = versiones(cliente, h.id)

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"})

    assert r.status_code == 201
    [despues] = versiones(cliente, h.id)  # nunca rigió: no hay historia que conservar (D10)
    assert despues["id"] == antes["id"] == r.json()["version"]["id"]
    assert (despues["horaInicio"], despues["vigenteDesde"], despues["vigenteHasta"]) == ("09:00:00", "2026-10-20", None)


def test_version_programada_se_modifica_en_el_lugar_sin_tocar_la_anterior(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)
    programada = DatosVersion(
        medico_id=carlos.id, dia_semana=2, hora_inicio=time(10), duracion_horas=12,
        frecuencia_semanas=1, fecha_ancla=date(2026, 9, 7),
    )
    nueva_version(sesion, h.id, programada, date(2026, 11, 3))

    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-11-03", "medicoId": None})

    assert r.status_code == 201
    assert [(v["medico"] and v["medico"]["id"], v["horaInicio"], v["vigenteDesde"], v["vigenteHasta"]) for v in versiones(cliente, h.id)] == [
        (carlos.id, "08:00:00", "2026-09-07", "2026-11-03"),
        (None, "10:00:00", "2026-11-03", None),
    ]


def test_horario_cerrado_no_admite_versiones(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id, hasta=date(2026, 10, 1))
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"})
    assert (r.status_code, r.json()["codigo"]) == (409, "HORARIO_SIN_VIGENCIA")


def test_version_igual_a_la_vigente(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "08:00"})
    assert (r.status_code, r.json()["codigo"]) == (422, "SIN_CAMBIOS")


def test_null_en_un_campo_que_no_es_el_medico(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "diaSemana": None})
    assert (r.status_code, r.json()["codigo"]) == (422, "VALIDACION")


def test_fecha_ancla_nueva_que_no_es_lunes(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "fechaAncla": "2026-10-13"})
    assert (r.status_code, r.json()["codigo"]) == (422, "FECHA_ANCLA_NO_LUNES")


def test_horario_inexistente(cliente, como_coordinador):
    r = cliente.post("/api/horarios/999999/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"})
    assert (r.status_code, r.json()["codigo"]) == (404, "HORARIO_NO_ENCONTRADO")


def test_designar_a_un_coordinador(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, None)
    r = cliente.post(f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "medicoId": como_coordinador.id})
    assert (r.status_code, r.json()["codigo"]) == (422, "TITULAR_INVALIDO")


def test_un_medico_no_modifica_horarios(cliente, sesion, reloj):
    medico = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, medico.id)
    r = cliente.post(
        f"/api/horarios/{h.id}/versiones", json={"desde": "2026-10-20", "horaInicio": "09:00"}, headers=encabezados(medico)
    )
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")

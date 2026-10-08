from datetime import date, time

from app.repos.horarios import DatosVersion, nueva_version
from fabricas import crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno


def test_cierre_corta_la_vigencia_y_el_calendario(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)

    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-20"})

    assert r.status_code == 200
    assert r.json()["horario"]["estado"] == "CON_TITULAR"  # hoy todavía rige
    assert r.json()["horario"]["versiones"][-1]["vigenteHasta"] == "2026-10-20"
    assert r.json()["turnosAfectados"] == []
    turnos = cliente.get("/api/turnos", params={"desde": "2026-10-13", "hasta": "2026-10-27"}).json()
    assert [t["fecha"] for t in turnos] == ["2026-10-13"]


def test_cierre_desde_hoy_deja_el_horario_cerrado(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-12"})
    assert r.json()["horario"]["estado"] == "CERRADO"


def test_cierre_informa_los_turnos_guardados(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)
    guardar_turno(sesion, h.id, date(2026, 10, 27))
    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-20"})
    assert [t["id"] for t in r.json()["turnosAfectados"]] == [f"{h.id}:2026-10-27"]


def test_horario_ya_cerrado(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-20"})
    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-20"})
    assert (r.status_code, r.json()["codigo"]) == (409, "HORARIO_SIN_VIGENCIA")


def test_cierre_con_una_version_posterior(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)
    programada = DatosVersion(
        medico_id=carlos.id, dia_semana=2, hora_inicio=time(10), duracion_horas=12,
        frecuencia_semanas=1, fecha_ancla=date(2026, 9, 7),
    )
    nueva_version(sesion, h.id, programada, date(2026, 11, 3))
    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-20"})
    assert (r.status_code, r.json()["codigo"]) == (409, "VERSION_POSTERIOR_EXISTENTE")


def test_cierre_en_el_pasado(cliente, sesion, como_coordinador):
    h = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos Lugones").id)
    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-11"})
    assert (r.status_code, r.json()["codigo"]) == (422, "FECHA_PASADA")


def test_cierre_de_horario_inexistente(cliente, como_coordinador):
    r = cliente.post("/api/horarios/999999/cierre", json={"desde": "2026-10-20"})
    assert (r.status_code, r.json()["codigo"]) == (404, "HORARIO_NO_ENCONTRADO")


def test_un_medico_no_cierra_horarios(cliente, sesion, reloj):
    medico = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, medico.id)
    r = cliente.post(f"/api/horarios/{h.id}/cierre", json={"desde": "2026-10-20"}, headers=encabezados(medico))
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")

from datetime import date, time

from app.modelos import EstadoUsuario, RolUsuario
from app.repos.horarios import DatosVersion, nueva_version
from fabricas import crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno


def titulares(cliente, desde, hasta) -> list[tuple[str, str | None]]:
    turnos = cliente.get("/api/turnos", params={"desde": desde, "hasta": hasta}).json()
    return [(t["fecha"], t["titular"]["nombre"] if t["titular"] else None) for t in turnos]


def test_baja_hoy_deja_sus_horarios_sin_titular_desde_mañana(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    martes = crear_horario_de_prueba(sesion, carlos.id, dia=2)
    lunes = crear_horario_de_prueba(sesion, carlos.id, dia=1, hora=time(20))

    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-12"})

    assert r.status_code == 200
    assert r.json()["usuario"]["estado"] == "BAJA"
    assert r.json()["usuario"]["fechaBaja"] == "2026-10-12"
    assert r.json()["horariosSinTitular"] == sorted([martes.id, lunes.id])
    # D24: activo hasta la fecha de baja inclusive; la guardia del lunes 12 sigue siendo suya.
    assert titulares(cliente, "2026-10-12", "2026-10-13") == [
        ("2026-10-12", "Carlos Lugones"),
        ("2026-10-13", None),
    ]
    [h] = [x for x in cliente.get("/api/horarios").json() if x["id"] == martes.id]
    assert [(v["medico"] and v["medico"]["id"], v["vigenteDesde"], v["vigenteHasta"]) for v in h["versiones"]] == [
        (carlos.id, "2026-09-07", "2026-10-13"),
        (None, "2026-10-13", None),
    ]


def test_baja_futura_conserva_las_guardias_hasta_esa_fecha(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    crear_horario_de_prueba(sesion, carlos.id)  # martes

    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-20"})

    assert r.status_code == 200
    assert titulares(cliente, "2026-10-13", "2026-10-27") == [
        ("2026-10-13", "Carlos Lugones"),
        ("2026-10-20", "Carlos Lugones"),
        ("2026-10-27", None),
    ]
    entra = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-12"}, headers=encabezados(carlos))
    assert entra.status_code == 200  # sigue entrando hasta el 20/10 inclusive (decisión 2)
    assert [x["vigenteHasta"] for x in r.json()["usuario"]["horarios"]] == ["2026-10-21"]


def test_baja_informa_los_turnos_guardados_de_sus_horarios(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)
    guardar_turno(sesion, h.id, date(2026, 10, 20))

    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-12"})

    [afectado] = r.json()["turnosAfectados"]
    assert afectado["id"] == f"{h.id}:2026-10-20"
    assert afectado["titular"] == {"id": carlos.id, "nombre": "Carlos Lugones"}  # la foto no cambia (D12)


def test_baja_respeta_una_version_futura_de_otro_medico(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    paula = crear_usuario(sesion, "Paula Méndez")
    h = crear_horario_de_prueba(sesion, carlos.id)
    de_paula = DatosVersion(
        medico_id=paula.id, dia_semana=2, hora_inicio=time(8), duracion_horas=12,
        frecuencia_semanas=1, fecha_ancla=date(2026, 9, 7),
    )
    nueva_version(sesion, h.id, de_paula, date(2026, 11, 3))

    cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-12"})

    [x] = [x for x in cliente.get("/api/horarios").json() if x["id"] == h.id]
    assert [(v["medico"] and v["medico"]["id"], v["vigenteDesde"], v["vigenteHasta"]) for v in x["versiones"]] == [
        (carlos.id, "2026-09-07", "2026-10-13"),
        (None, "2026-10-13", "2026-11-03"),
        (paula.id, "2026-11-03", None),
    ]


def test_baja_con_una_version_futura_propia_la_deja_sin_titular_en_el_lugar(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id)
    nueva_version(
        sesion, h.id,
        DatosVersion(medico_id=carlos.id, dia_semana=2, hora_inicio=time(9), duracion_horas=12,
                     frecuencia_semanas=1, fecha_ancla=date(2026, 9, 7)),
        date(2026, 11, 3),
    )

    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-12"})

    assert r.status_code == 200
    assert r.json()["horariosSinTitular"] == [h.id]
    [x] = [x for x in cliente.get("/api/horarios").json() if x["id"] == h.id]
    assert [(v["medico"] and v["medico"]["id"], v["horaInicio"], v["vigenteDesde"], v["vigenteHasta"]) for v in x["versiones"]] == [
        (carlos.id, "08:00:00", "2026-09-07", "2026-10-13"),
        (None, "08:00:00", "2026-10-13", "2026-11-03"),
        (None, "09:00:00", "2026-11-03", None),
    ]


def test_baja_de_quien_tiene_un_horario_que_todavia_no_empezo(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    h = crear_horario_de_prueba(sesion, carlos.id, desde=date(2026, 11, 3))

    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-12"})

    assert r.status_code == 200
    assert r.json()["horariosSinTitular"] == [h.id]
    [x] = [x for x in cliente.get("/api/horarios").json() if x["id"] == h.id]
    assert [(v["medico"], v["vigenteDesde"]) for v in x["versiones"]] == [(None, "2026-11-03")]


def test_baja_de_un_pendiente(cliente, sesion, como_coordinador):
    pendiente = crear_usuario(sesion, "Registro equivocado", estado=EstadoUsuario.PENDIENTE)
    r = cliente.post(f"/api/usuarios/{pendiente.id}/baja", json={"fechaBaja": "2026-10-12"})
    assert r.status_code == 200
    assert r.json()["usuario"]["estado"] == "BAJA"
    assert pendiente.id in [u["id"] for u in cliente.get("/api/usuarios").json()]  # nunca se borra (D24)


def test_baja_en_el_pasado(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-11"})
    assert (r.status_code, r.json()["codigo"]) == (422, "FECHA_PASADA")


def test_baja_de_un_coordinador(cliente, sesion, como_coordinador):
    otro = crear_usuario(sesion, "Otro coordinador", rol=RolUsuario.COORDINADOR)
    r = cliente.post(f"/api/usuarios/{otro.id}/baja", json={"fechaBaja": "2026-10-12"})
    assert (r.status_code, r.json()["codigo"]) == (422, "BAJA_SOLO_MEDICOS")


def test_baja_repetida(cliente, sesion, como_coordinador):
    baja = crear_usuario(sesion, "Se fue", estado=EstadoUsuario.BAJA)
    r = cliente.post(f"/api/usuarios/{baja.id}/baja", json={"fechaBaja": "2026-10-12"})
    assert (r.status_code, r.json()["codigo"]) == (409, "USUARIO_DADO_DE_BAJA")


def test_baja_de_usuario_inexistente(cliente, como_coordinador):
    r = cliente.post("/api/usuarios/999999/baja", json={"fechaBaja": "2026-10-12"})
    assert (r.status_code, r.json()["codigo"]) == (404, "USUARIO_NO_ENCONTRADO")


def test_un_medico_no_da_de_baja(cliente, sesion, reloj):
    medico = crear_usuario(sesion, "Carlos Lugones")
    otro = crear_usuario(sesion, "Paula Méndez")
    r = cliente.post(f"/api/usuarios/{otro.id}/baja", json={"fechaBaja": "2026-10-12"}, headers=encabezados(medico))
    assert (r.status_code, r.json()["codigo"]) == (403, "SIN_PERMISO")

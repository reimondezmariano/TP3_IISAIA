from datetime import date, time, timedelta

import pytest
from sqlalchemy import event

from app.modelos import RolUsuario
from app.repos.horarios import DatosVersion, crear_horario
from fabricas import crear_usuario, encabezados


@pytest.fixture(autouse=True)
def con_sesion(cliente, sesion):
    """GET /api/turnos exige un usuario activo: todas las consultas de este archivo van con sesión."""
    cliente.headers.update(encabezados(crear_usuario(sesion, "Médico que consulta")))


def horario(sesion, medico_id, dia, hora, dur, frec=1, ancla=date(2026, 9, 7)):
    datos = DatosVersion(
        medico_id=medico_id,
        dia_semana=dia,
        hora_inicio=hora,
        duracion_horas=dur,
        frecuencia_semanas=frec,
        fecha_ancla=ancla,
    )
    return crear_horario(sesion, datos, date(2026, 9, 7))


def test_turnos_formato_exacto(cliente, sesion):
    florencia = crear_usuario(sesion, "Florencia Lucca")
    sabado = horario(sesion, florencia.id, dia=6, hora=time(8), dur=12)

    r = cliente.get("/api/turnos", params={"desde": "2026-10-17", "hasta": "2026-10-17"})

    assert r.status_code == 200
    assert r.json() == [
        {
            "id": f"{sabado.id}:2026-10-17",
            "horarioId": sabado.id,
            "fecha": "2026-10-17",
            "inicio": "2026-10-17T08:00:00-03:00",
            "fin": "2026-10-17T20:00:00-03:00",
            "duracionHoras": 12,
            "titular": {"id": florencia.id, "nombre": "Florencia Lucca"},
            "vacante": None,
            "asignado": None,
            "sinCobertura": False,
            "miPostulacionId": None,
            "cantidadPostulantes": 0,
        }
    ]


def test_turno_que_cruza_medianoche_aparece_el_dia_siguiente(cliente, sesion):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    viernes = horario(sesion, carlos.id, dia=5, hora=time(20), dur=12)

    r = cliente.get("/api/turnos", params={"desde": "2026-10-17", "hasta": "2026-10-17"})

    [turno] = r.json()
    assert turno["id"] == f"{viernes.id}:2026-10-16"
    assert turno["fin"] == "2026-10-17T08:00:00-03:00"


def test_horario_sin_titular_sale_con_titular_null(cliente, sesion):
    horario(sesion, None, dia=3, hora=time(8), dur=12)
    [turno] = cliente.get("/api/turnos", params={"desde": "2026-10-14", "hasta": "2026-10-14"}).json()
    assert turno["titular"] is None


def test_hasta_anterior_a_desde_es_rango_invalido(cliente):
    r = cliente.get("/api/turnos", params={"desde": "2026-10-18", "hasta": "2026-10-12"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "RANGO_INVALIDO"


@pytest.mark.parametrize("desde,hasta", [("0001-01-01", "0001-01-10"), ("9999-12-20", "9999-12-31")])
def test_fechas_en_los_extremos_del_calendario_son_422_con_formato_de_error(cliente, desde, hasta):
    r = cliente.get("/api/turnos", params={"desde": desde, "hasta": hasta})
    assert r.status_code == 422
    assert r.json()["codigo"] == "FECHA_FUERA_DE_RANGO"
    assert r.json()["mensaje"]


def test_rango_de_62_dias_se_acepta_y_63_no(cliente):
    ok = cliente.get("/api/turnos", params={"desde": "2026-10-01", "hasta": "2026-12-01"})
    assert ok.status_code == 200
    grande = cliente.get("/api/turnos", params={"desde": "2026-10-01", "hasta": "2026-12-02"})
    assert grande.status_code == 422
    assert grande.json()["codigo"] == "RANGO_DEMASIADO_GRANDE"


def test_falta_un_parametro_es_error_de_validacion(cliente):
    r = cliente.get("/api/turnos", params={"desde": "2026-10-12"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDACION"


def test_fecha_imposible_es_error_de_validacion(cliente):
    r = cliente.get("/api/turnos", params={"desde": "2026-02-30", "hasta": "2026-03-02"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDACION"


def test_sin_horarios_devuelve_lista_vacia(cliente):
    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-18"})
    assert r.status_code == 200
    assert r.json() == []


def test_turno_con_vacante_abierta_trae_id_urgencia_y_generador(cliente, sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    horario_martes = horario(sesion, carlos.id, dia=2, hora=time(8), dur=12)
    cliente.headers.update(encabezados(carlos))
    # Reloj fijo: lunes 12/10 09:00. El martes 13/10 está a 23 h (urgente); el del 20/10 no.
    urgente = cliente.post(f"/api/turnos/{horario_martes.id}:2026-10-13/vacantes", json={"motivo": "privado"}).json()
    lejano = cliente.post(f"/api/turnos/{horario_martes.id}:2026-10-20/vacantes", json={}).json()

    turnos = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-20"}).json()

    por_fecha = {t["fecha"]: t for t in turnos}
    assert por_fecha["2026-10-13"]["vacante"] == {
        "id": urgente["id"],
        "urgente": True,
        "generadaPor": {"id": carlos.id, "nombre": "Carlos Lugones"},
    }
    assert por_fecha["2026-10-20"]["vacante"]["id"] == lejano["id"]
    assert por_fecha["2026-10-20"]["vacante"]["urgente"] is False
    assert "motivo" not in por_fecha["2026-10-13"]["vacante"]


def test_la_vacante_retirada_o_cubierta_no_aparece(cliente, sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    horario_martes = horario(sesion, carlos.id, dia=2, hora=time(8), dur=12)
    cliente.headers.update(encabezados(carlos))
    vacante = cliente.post(f"/api/turnos/{horario_martes.id}:2026-10-20/vacantes", json={}).json()
    cliente.post(f"/api/vacantes/{vacante['id']}/retiro")

    [turno] = cliente.get("/api/turnos", params={"desde": "2026-10-20", "hasta": "2026-10-20"}).json()

    assert turno["vacante"] is None


def test_turno_asignado_trae_al_asignado_vigente(cliente, sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    mariano = crear_usuario(sesion, "Mariano Reimondez")
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    martes = horario(sesion, carlos.id, dia=2, hora=time(8), dur=12)
    turno_id = f"{martes.id}:2026-10-20"
    cliente.post(f"/api/turnos/{turno_id}/vacantes", json={}, headers=encabezados(carlos))
    cliente.post(f"/api/turnos/{turno_id}/postulaciones", headers=encabezados(mariano))
    r = cliente.put(f"/api/turnos/{turno_id}/asignacion", json={"medicoId": mariano.id}, headers=encabezados(enzo))
    assert r.status_code == 200

    [turno] = cliente.get("/api/turnos", params={"desde": "2026-10-20", "hasta": "2026-10-20"}).json()

    assert turno["asignado"] == {"id": mariano.id, "nombre": "Mariano Reimondez"}
    assert turno["vacante"] is None
    assert turno["sinCobertura"] is False


def test_turno_marcado_sin_cobertura(cliente, sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    martes = horario(sesion, carlos.id, dia=2, hora=time(8), dur=12)
    turno_id = f"{martes.id}:2026-10-13"
    cliente.post(f"/api/turnos/{turno_id}/vacantes", json={}, headers=encabezados(carlos))
    reloj.avanzar(timedelta(days=1, minutes=30))  # martes 13/10 09:30: el turno empezó
    r = cliente.post(f"/api/turnos/{turno_id}/sin-cobertura", headers=encabezados(enzo))
    assert r.status_code == 200

    [turno] = cliente.get("/api/turnos", params={"desde": "2026-10-13", "hasta": "2026-10-13"}).json()

    assert turno["sinCobertura"] is True
    assert turno["vacante"] is None
    assert turno["asignado"] is None


def test_mi_postulacion_activa_solo_para_quien_consulta(cliente, sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    mariano = crear_usuario(sesion, "Mariano Reimondez")
    florencia = crear_usuario(sesion, "Florencia Lucca")
    martes = horario(sesion, carlos.id, dia=2, hora=time(8), dur=12)
    turno_id = f"{martes.id}:2026-10-20"
    cliente.post(f"/api/turnos/{turno_id}/vacantes", json={}, headers=encabezados(carlos))
    postulacion = cliente.post(f"/api/turnos/{turno_id}/postulaciones", headers=encabezados(mariano)).json()
    rango = {"desde": "2026-10-20", "hasta": "2026-10-20"}

    [para_mariano] = cliente.get("/api/turnos", params=rango, headers=encabezados(mariano)).json()
    [para_florencia] = cliente.get("/api/turnos", params=rango, headers=encabezados(florencia)).json()
    assert para_mariano["miPostulacionId"] == postulacion["id"]
    assert para_florencia["miPostulacionId"] is None

    cliente.post(f"/api/postulaciones/{postulacion['id']}/retiro", headers=encabezados(mariano))
    [retirada] = cliente.get("/api/turnos", params=rango, headers=encabezados(mariano)).json()
    assert retirada["miPostulacionId"] is None


def test_cantidad_de_postulantes_cuenta_solo_las_activas(cliente, sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    mariano = crear_usuario(sesion, "Mariano Reimondez")
    florencia = crear_usuario(sesion, "Florencia Lucca")
    ana = crear_usuario(sesion, "Ana Pérez")
    martes = horario(sesion, carlos.id, dia=2, hora=time(8), dur=12)
    turno_id = f"{martes.id}:2026-10-20"
    cliente.post(f"/api/turnos/{turno_id}/vacantes", json={}, headers=encabezados(carlos))
    for medico in (mariano, florencia):
        cliente.post(f"/api/turnos/{turno_id}/postulaciones", headers=encabezados(medico))
    de_ana = cliente.post(f"/api/turnos/{turno_id}/postulaciones", headers=encabezados(ana)).json()
    cliente.post(f"/api/postulaciones/{de_ana['id']}/retiro", headers=encabezados(ana))

    turnos = cliente.get("/api/turnos", params={"desde": "2026-10-13", "hasta": "2026-10-20"}).json()

    por_fecha = {t["fecha"]: t for t in turnos}
    assert por_fecha["2026-10-20"]["cantidadPostulantes"] == 2
    assert por_fecha["2026-10-13"]["cantidadPostulantes"] == 0  # turno sin fila (D11)


def test_la_cantidad_de_consultas_no_crece_con_los_turnos(cliente, sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    mariano = crear_usuario(sesion, "Mariano Reimondez")
    martes = horario(sesion, carlos.id, dia=2, hora=time(8), dur=12)
    for fecha in ("2026-10-20", "2026-10-27", "2026-11-03"):
        turno_id = f"{martes.id}:{fecha}"
        cliente.post(f"/api/turnos/{turno_id}/vacantes", json={}, headers=encabezados(carlos))
        cliente.post(f"/api/turnos/{turno_id}/postulaciones", headers=encabezados(mariano))

    def contar_consultas(desde, hasta):
        consultas = []
        conexion = sesion.connection()
        escuchar = lambda *args: consultas.append(args[2])  # noqa: E731
        event.listen(conexion, "before_cursor_execute", escuchar)
        try:
            r = cliente.get("/api/turnos", params={"desde": desde, "hasta": hasta})
        finally:
            event.remove(conexion, "before_cursor_execute", escuchar)
        assert r.status_code == 200
        return len(consultas)

    contar_consultas("2026-10-20", "2026-10-20")  # la primera consulta consolida; se descarta
    un_turno = contar_consultas("2026-10-20", "2026-10-20")
    tres_turnos = contar_consultas("2026-10-20", "2026-11-03")

    assert tres_turnos == un_turno

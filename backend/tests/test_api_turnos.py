from datetime import date, time

from app.repos.horarios import DatosVersion, crear_horario
from fabricas import crear_usuario


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

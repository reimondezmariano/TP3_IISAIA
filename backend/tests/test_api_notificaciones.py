from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.dominio.notificaciones import TipoNotificacion
from app.modelos import RolUsuario
from app.servicios.notificaciones import notificar
from fabricas import abrir_vacante, crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
ANTES = datetime(2026, 10, 12, 8, 0, tzinfo=ZONA)


def test_lista_solo_las_propias_mas_nuevas_primero_con_formato(cliente, sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    beto = crear_usuario(sesion, "Beto")
    turno = guardar_turno(sesion, crear_horario_de_prueba(sesion, ana.id).id, date(2026, 10, 13))
    [vieja] = notificar(sesion, [ana.id], TipoNotificacion.VACANTE_URGENTE, "Vieja", ANTES, turno=turno, datos={"a": 1})
    [nueva] = notificar(sesion, [ana.id], TipoNotificacion.VACANTE_URGENTE, "Nueva", ANTES + timedelta(minutes=30))
    notificar(sesion, [beto.id], TipoNotificacion.VACANTE_URGENTE, "Ajena", ANTES)
    cliente.headers.update(encabezados(ana))

    r = cliente.get("/api/notificaciones")

    assert r.status_code == 200
    assert r.json() == [
        {
            "id": nueva.id,
            "tipo": "VACANTE_URGENTE",
            "mensaje": "Nueva",
            "turnoId": None,
            "datos": {},
            "creadaEn": "2026-10-12T08:30:00-03:00",
            "leidaEn": None,
        },
        {
            "id": vieja.id,
            "tipo": "VACANTE_URGENTE",
            "mensaje": "Vieja",
            "turnoId": f"{turno.horario_id}:2026-10-13",
            "datos": {"a": 1},
            "creadaEn": "2026-10-12T08:00:00-03:00",
            "leidaEn": None,
        },
    ]


def test_marcar_leida_y_filtrar_las_no_leidas(cliente, sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    [leida, pendiente] = [
        notificar(sesion, [ana.id], TipoNotificacion.VACANTE_URGENTE, texto, ANTES)[0] for texto in ("1", "2")
    ]
    cliente.headers.update(encabezados(ana))

    r = cliente.post(f"/api/notificaciones/{leida.id}/leida")
    assert r.status_code == 200
    assert r.json()["leidaEn"] == "2026-10-12T09:00:00-03:00"

    ids = [n["id"] for n in cliente.get("/api/notificaciones", params={"soloNoLeidas": "true"}).json()]
    assert ids == [pendiente.id]


def test_marcar_leida_dos_veces_conserva_la_primera_hora(cliente, sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    [n] = notificar(sesion, [ana.id], TipoNotificacion.VACANTE_URGENTE, "x", ANTES)
    cliente.headers.update(encabezados(ana))
    cliente.post(f"/api/notificaciones/{n.id}/leida")
    reloj.avanzar(timedelta(hours=1))
    assert cliente.post(f"/api/notificaciones/{n.id}/leida").json()["leidaEn"] == "2026-10-12T09:00:00-03:00"


def test_no_se_marca_una_notificacion_ajena(cliente, sesion, reloj):
    # Review Focus 5: mismo 404 que una inexistente.
    ana = crear_usuario(sesion, "Ana")
    beto = crear_usuario(sesion, "Beto")
    [ajena] = notificar(sesion, [beto.id], TipoNotificacion.VACANTE_URGENTE, "x", ANTES)
    cliente.headers.update(encabezados(ana))
    for notificacion_id in (ajena.id, 999999):
        r = cliente.post(f"/api/notificaciones/{notificacion_id}/leida")
        assert r.status_code == 404
        assert r.json()["codigo"] == "NOTIFICACION_NO_ENCONTRADA"
    assert ajena.leida_en is None


def test_devuelve_como_maximo_50(cliente, sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    for i in range(51):
        notificar(sesion, [ana.id], TipoNotificacion.VACANTE_URGENTE, str(i), ANTES + timedelta(seconds=i))
    cliente.headers.update(encabezados(ana))
    respuesta = cliente.get("/api/notificaciones").json()
    assert len(respuesta) == 50
    assert respuesta[0]["mensaje"] == "50"


def test_consultar_emite_las_alertas_pendientes(cliente, sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    turno = guardar_turno(sesion, crear_horario_de_prueba(sesion, ana.id).id, date(2026, 10, 13))
    abrir_vacante(sesion, turno, ana.id, datetime(2026, 10, 9, tzinfo=ZONA))
    cliente.headers.update(encabezados(enzo))

    [alerta] = cliente.get("/api/notificaciones").json()

    assert alerta["tipo"] == "ALERTA_SIN_COBERTURA"
    assert alerta["datos"] == {"umbral": "24H"}
    assert alerta["turnoId"] == f"{turno.horario_id}:2026-10-13"


def test_sin_sesion_responde_401(cliente):
    assert cliente.get("/api/notificaciones").status_code == 401

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from fabricas import abrir_vacante, crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def test_horas_sin_cobertura_por_mes(cliente, sesion, como_coordinador):
    ana = crear_usuario(sesion, "Ana")
    con_titular = crear_horario_de_prueba(sesion, ana.id)  # martes 08 a 20: lo hace Ana, no cuenta
    crear_horario_de_prueba(sesion, None)  # martes 08 a 20 sin titular (BAJA): 12 h cada martes
    turno = guardar_turno(sesion, con_titular.id, date(2026, 10, 6))
    abrir_vacante(sesion, turno, ana.id, datetime(2026, 10, 1, tzinfo=ZONA))  # quedó abierta al terminar

    r = cliente.get("/api/indicadores/sin-cobertura", params={"desde": "2026-09", "hasta": "2026-11"})

    assert r.status_code == 200
    assert r.json() == [
        {"mes": "2026-09", "horas": 48.0, "turnos": 4},
        {"mes": "2026-10", "horas": 24.0, "turnos": 2},
        {"mes": "2026-11", "horas": 0.0, "turnos": 0},
    ]


@pytest.mark.parametrize(
    "desde,hasta,codigo",
    [
        ("2026-10", "2026-09", "RANGO_INVALIDO"),
        ("2024-01", "2026-12", "RANGO_DEMASIADO_GRANDE"),
        ("2026-13", "2026-12", "VALIDACION"),
        ("0000-01", "0000-02", "VALIDACION"),
    ],
)
def test_rangos_invalidos_son_422(cliente, como_coordinador, desde, hasta, codigo):
    r = cliente.get("/api/indicadores/sin-cobertura", params={"desde": desde, "hasta": hasta})
    assert r.status_code == 422
    assert r.json()["codigo"] == codigo


def test_un_medico_no_ve_el_indicador(cliente, sesion, reloj):
    cliente.headers.update(encabezados(crear_usuario(sesion, "Ana")))
    r = cliente.get("/api/indicadores/sin-cobertura", params={"desde": "2026-10", "hasta": "2026-10"})
    assert r.status_code == 403

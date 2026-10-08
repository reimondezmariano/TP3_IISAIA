from datetime import date

import pytest

from app.modelos import EstadoUsuario, RolUsuario
from fabricas import crear_horario_de_prueba, crear_usuario, encabezados


def test_lista_de_usuarios_formato_exacto(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones", email="carlos@prueba.test")
    vigente = crear_horario_de_prueba(sesion, carlos.id)
    crear_horario_de_prueba(sesion, carlos.id, dia=5, hasta=date(2026, 10, 1))  # terminado: no se lista

    r = cliente.get("/api/usuarios")

    assert r.status_code == 200
    [carlos_out] = [u for u in r.json() if u["id"] == carlos.id]
    assert carlos_out == {
        "id": carlos.id,
        "nombre": "Carlos Lugones",
        "email": "carlos@prueba.test",
        "rol": "MEDICO",
        "estado": "ACTIVO",
        "fechaBaja": None,
        "horarios": [
            {
                "horarioId": vigente.id,
                "diaSemana": 2,
                "horaInicio": "08:00:00",
                "duracionHoras": 12,
                "frecuenciaSemanas": 1,
                "fechaAncla": "2026-09-07",
                "vigenteDesde": "2026-09-07",
                "vigenteHasta": None,
            }
        ],
    }


def test_lista_de_usuarios_incluye_pendientes_bajas_y_coordinadores_ordenados_por_nombre(cliente, sesion, como_coordinador):
    crear_usuario(sesion, "Zoe Pendiente", estado=EstadoUsuario.PENDIENTE)
    crear_usuario(sesion, "Ana Baja", estado=EstadoUsuario.BAJA, fecha_baja=date(2026, 10, 1))

    usuarios = cliente.get("/api/usuarios").json()

    assert [u["nombre"] for u in usuarios] == ["Ana Baja", "Enzo", "Zoe Pendiente"]
    assert usuarios[0]["fechaBaja"] == "2026-10-01"
    assert usuarios[1]["rol"] == "COORDINADOR"
    assert usuarios[2]["estado"] == "PENDIENTE"


def test_lista_de_horarios_con_estado_calculado(cliente, sesion, como_coordinador):
    paula = crear_usuario(sesion, "Paula Méndez")
    con_titular = crear_horario_de_prueba(sesion, paula.id)
    sin_titular = crear_horario_de_prueba(sesion, None)
    cerrado = crear_horario_de_prueba(sesion, paula.id, hasta=date(2026, 10, 1))

    r = cliente.get("/api/horarios")

    assert r.status_code == 200
    por_id = {h["id"]: h for h in r.json()}
    assert por_id[con_titular.id]["estado"] == "CON_TITULAR"
    assert por_id[sin_titular.id]["estado"] == "SIN_TITULAR"
    assert por_id[cerrado.id]["estado"] == "CERRADO"
    assert por_id[con_titular.id]["versiones"] == [
        {
            "id": por_id[con_titular.id]["versiones"][0]["id"],
            "medico": {"id": paula.id, "nombre": "Paula Méndez"},
            "diaSemana": 2,
            "horaInicio": "08:00:00",
            "duracionHoras": 12,
            "frecuenciaSemanas": 1,
            "fechaAncla": "2026-09-07",
            "vigenteDesde": "2026-09-07",
            "vigenteHasta": None,
        }
    ]
    assert por_id[sin_titular.id]["versiones"][0]["medico"] is None


@pytest.mark.parametrize("ruta", ["/api/usuarios", "/api/horarios"])
def test_un_medico_no_ve_el_staff(cliente, sesion, reloj, ruta):
    medico = crear_usuario(sesion, "Carlos Lugones")
    r = cliente.get(ruta, headers=encabezados(medico))
    assert r.status_code == 403
    assert r.json()["codigo"] == "SIN_PERMISO"

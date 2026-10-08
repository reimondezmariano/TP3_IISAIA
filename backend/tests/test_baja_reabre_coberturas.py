from datetime import date, datetime, time

from sqlalchemy import select

from app.modelos import EstadoVacante, EventoTurno, RolUsuario, TipoEventoTurno, Turno, Vacante
from fabricas import ZONA, crear_horario_de_prueba, crear_usuario, guardar_turno


def vacante_abierta(sesion, turno_id) -> Vacante | None:
    return sesion.scalar(select(Vacante).where(Vacante.turno_id == turno_id, Vacante.estado == EstadoVacante.ABIERTA))


def test_baja_reabre_las_coberturas_posteriores(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    paula = crear_usuario(sesion, "Paula Méndez")
    de_paula = crear_horario_de_prueba(sesion, paula.id, dia=4)  # jueves
    cubre_el_15 = guardar_turno(sesion, de_paula.id, date(2026, 10, 15), asignado_id=carlos.id)

    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-12"})

    assert r.status_code == 200
    reabiertas = r.json()["coberturasReabiertas"]
    assert [t["id"] for t in reabiertas] == [f"{de_paula.id}:2026-10-15"]
    assert reabiertas[0]["asignado"]["id"] == carlos.id  # el que tenía antes de reabrirse
    vacante = vacante_abierta(sesion, cubre_el_15.id)
    assert vacante is not None
    assert vacante.generada_por_id == como_coordinador.id
    sesion.expire_all()
    assert sesion.get(Turno, cubre_el_15.id).asignado_id is None
    evento = sesion.scalar(
        select(EventoTurno).where(
            EventoTurno.turno_id == cubre_el_15.id, EventoTurno.tipo == TipoEventoTurno.VACANTE_GENERADA
        )
    )
    assert evento.datos["asignado_anterior_id"] == carlos.id


def test_baja_futura_conserva_las_coberturas_hasta_su_fecha(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    paula = crear_usuario(sesion, "Paula Méndez")
    de_paula = crear_horario_de_prueba(sesion, paula.id, dia=4)
    antes = guardar_turno(sesion, de_paula.id, date(2026, 10, 15), asignado_id=carlos.id)
    despues = guardar_turno(sesion, de_paula.id, date(2026, 10, 22), asignado_id=carlos.id)

    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-15"})

    assert r.status_code == 200
    assert vacante_abierta(sesion, antes.id) is None
    assert vacante_abierta(sesion, despues.id) is not None


def test_cobertura_consolidada_no_se_reabre(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    paula = crear_usuario(sesion, "Paula Méndez")
    de_paula = crear_horario_de_prueba(sesion, paula.id, dia=1, hora=time(0), dur=6)
    hecha = guardar_turno(
        sesion, de_paula.id, date(2026, 10, 12), asignado_id=carlos.id,
        consolidado_en=datetime(2026, 10, 12, 7, tzinfo=ZONA),
    )

    r = cliente.post(f"/api/usuarios/{carlos.id}/baja", json={"fechaBaja": "2026-10-12"})

    assert r.status_code == 200
    assert r.json()["coberturasReabiertas"] == []
    assert vacante_abierta(sesion, hecha.id) is None


def test_medico_que_pasa_a_coordinador_libera_sus_coberturas(cliente, sesion, como_coordinador):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    paula = crear_usuario(sesion, "Paula Méndez")
    de_paula = crear_horario_de_prueba(sesion, paula.id, dia=4)
    cubre = guardar_turno(sesion, de_paula.id, date(2026, 10, 15), asignado_id=carlos.id)

    r = cliente.patch(f"/api/usuarios/{carlos.id}", json={"rol": "COORDINADOR"})

    assert r.status_code == 200
    assert [t["id"] for t in r.json()["coberturasReabiertas"]] == [f"{de_paula.id}:2026-10-15"]
    assert vacante_abierta(sesion, cubre.id) is not None


def test_coordinador_que_pasa_a_medico_no_reabre_nada(cliente, sesion, como_coordinador):
    beto = crear_usuario(sesion, "Beto", rol=RolUsuario.COORDINADOR)

    r = cliente.patch(f"/api/usuarios/{beto.id}", json={"rol": "MEDICO"})

    assert r.status_code == 200
    assert r.json()["coberturasReabiertas"] == []

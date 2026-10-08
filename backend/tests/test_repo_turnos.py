from datetime import date, datetime

import pytest
from sqlalchemy import func, select, update

from app.errores import ErrorDominio
from app.modelos import Turno, VersionHorario
from app.repos.turnos import bloquear_turnos, materializar_turno
from fabricas import ZONA, bloqueado_hasta_commit, crear_horario_de_prueba, crear_usuario


def cantidad_de_turnos(sesion) -> int:
    return sesion.scalar(select(func.count()).select_from(Turno))


def test_materializa_con_la_foto_de_la_version(sesion):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    horario = crear_horario_de_prueba(sesion, carlos.id)  # martes 08:00 a 20:00

    turno = materializar_turno(sesion, f"{horario.id}:2026-10-13", ZONA)

    version = sesion.scalars(select(VersionHorario).where(VersionHorario.horario_id == horario.id)).one()
    assert (turno.horario_id, turno.fecha, turno.version_id) == (horario.id, date(2026, 10, 13), version.id)
    assert turno.titular_id == carlos.id
    assert turno.inicio == datetime(2026, 10, 13, 8, tzinfo=ZONA)
    assert turno.fin == datetime(2026, 10, 13, 20, tzinfo=ZONA)
    assert turno.asignado_id is None and turno.consolidado_en is None


def test_es_idempotente(sesion):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos").id)
    primero = materializar_turno(sesion, f"{horario.id}:2026-10-13", ZONA)
    segundo = materializar_turno(sesion, f"{horario.id}:2026-10-13", ZONA)
    assert primero.id == segundo.id
    assert cantidad_de_turnos(sesion) == 1


def test_turno_que_el_horario_no_produce_responde_404_y_no_guarda(sesion):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos").id)  # solo martes
    with pytest.raises(ErrorDominio) as error:
        materializar_turno(sesion, f"{horario.id}:2026-10-14", ZONA)  # miércoles
    assert (error.value.codigo, error.value.status) == ("TURNO_NO_ENCONTRADO", 404)
    assert cantidad_de_turnos(sesion) == 0


def test_horario_inexistente_responde_404(sesion):
    with pytest.raises(ErrorDominio) as error:
        materializar_turno(sesion, "99999:2026-10-13", ZONA)
    assert error.value.codigo == "TURNO_NO_ENCONTRADO"


def test_fecha_en_el_extremo_del_calendario_responde_404_y_no_desborda(sesion):
    with pytest.raises(ErrorDominio) as error:
        materializar_turno(sesion, "1:0001-01-01", ZONA)
    assert error.value.codigo == "TURNO_NO_ENCONTRADO"


def test_usa_la_foto_guardada_si_la_plantilla_cambio(sesion):
    carlos = crear_usuario(sesion, "Carlos")
    paula = crear_usuario(sesion, "Paula")
    horario = crear_horario_de_prueba(sesion, carlos.id)
    materializar_turno(sesion, f"{horario.id}:2026-10-13", ZONA)

    sesion.execute(update(VersionHorario).where(VersionHorario.horario_id == horario.id).values(medico_id=paula.id))
    turno = materializar_turno(sesion, f"{horario.id}:2026-10-13", ZONA)

    assert turno.titular_id == carlos.id  # D11, D12: la foto no se recalcula


def test_un_turno_guardado_sigue_existiendo_aunque_se_cierre_el_horario(sesion):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Carlos").id)
    guardado = materializar_turno(sesion, f"{horario.id}:2026-10-13", ZONA)
    sesion.execute(
        update(VersionHorario).where(VersionHorario.horario_id == horario.id).values(vigente_hasta=date(2026, 10, 13))
    )
    sesion.expire_all()

    assert materializar_turno(sesion, f"{horario.id}:2026-10-13", ZONA).id == guardado.id
    with pytest.raises(ErrorDominio):  # un turno nuevo del horario cerrado ya no existe
        materializar_turno(sesion, f"{horario.id}:2026-10-20", ZONA)


def test_bloquear_turnos_ordena_por_horario_y_fecha(sesion):
    carlos = crear_usuario(sesion, "Carlos")
    h1 = crear_horario_de_prueba(sesion, carlos.id)
    h2 = crear_horario_de_prueba(sesion, carlos.id)
    pedidos = [f"{h2.id}:2026-10-20", f"{h1.id}:2026-10-20", f"{h2.id}:2026-10-13", f"{h1.id}:2026-10-13"]

    turnos = bloquear_turnos(sesion, pedidos, ZONA)

    assert [(t.horario_id, t.fecha) for t in turnos] == [
        (h1.id, date(2026, 10, 13)),
        (h1.id, date(2026, 10, 20)),
        (h2.id, date(2026, 10, 13)),
        (h2.id, date(2026, 10, 20)),
    ]
    assert cantidad_de_turnos(sesion) == 4


@pytest.mark.commit_real
def test_dos_materializaciones_simultaneas_dejan_una_fila(fabrica_sesiones):
    with fabrica_sesiones() as s:
        horario_id = crear_horario_de_prueba(s, crear_usuario(s, "Carlos").id).id
        s.commit()
    turno_id = f"{horario_id}:2026-10-13"

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        primero = materializar_turno(s1, turno_id, ZONA)  # inserta y retiene la fila hasta confirmar
        primero_id = primero.id
        resultado = bloqueado_hasta_commit(s1, lambda: materializar_turno(s2, turno_id, ZONA))

        assert "error" not in resultado, resultado.get("error")
        assert resultado["valor"].id == primero_id

    with fabrica_sesiones() as s:
        assert cantidad_de_turnos(s) == 1

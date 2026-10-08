from datetime import date, datetime, time

import pytest
from psycopg.errors import LockNotAvailable
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.errores import ErrorDominio
from app.modelos import EstadoUsuario, RolUsuario, Usuario, VersionHorario
from app.reloj import RelojFijo
from app.servicios.plantilla import abrir_version
from app.servicios.usuarios import cambiar_rol, dar_de_baja
from fabricas import HOY, ZONA, bloqueado_hasta_commit, crear_horario_de_prueba, crear_usuario, encabezados

AHORA = datetime(2026, 10, 12, 9, 0, tzinfo=ZONA)
RELOJ = RelojFijo(AHORA)


@pytest.mark.commit_real
def test_dos_cambios_simultaneos_desde_la_misma_fecha(fabrica_sesiones):
    with fabrica_sesiones() as s:
        horario_id = crear_horario_de_prueba(s, None).id
        s.commit()

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        # Desde hoy: la versión que abre el primero ya rige, así que el segundo no puede modificarla en el lugar.
        abrir_version(s1, horario_id, {"hora_inicio": time(9)}, HOY, HOY, AHORA, ZONA)
        resultado = bloqueado_hasta_commit(
            s1, lambda: abrir_version(s2, horario_id, {"hora_inicio": time(10)}, HOY, HOY, AHORA, ZONA)
        )

    assert isinstance(resultado.get("error"), ErrorDominio)
    assert resultado["error"].codigo == "VERSION_EN_ESA_FECHA"


@pytest.mark.commit_real
def test_dos_coordinadores_no_pueden_quitarse_el_rol_a_la_vez(fabrica_sesiones):
    with fabrica_sesiones() as s:
        ana = crear_usuario(s, "Ana", rol=RolUsuario.COORDINADOR)
        beto = crear_usuario(s, "Beto", rol=RolUsuario.COORDINADOR)
        s.commit()
        ana_id, beto_id = ana.id, beto.id

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        cambiar_rol(s1, beto_id, RolUsuario.MEDICO, s1.get(Usuario, ana_id), RELOJ)  # Ana le quita el rol a Beto
        resultado = bloqueado_hasta_commit(s1, lambda: cambiar_rol(s2, ana_id, RolUsuario.MEDICO, s2.get(Usuario, beto_id), RELOJ))

    assert isinstance(resultado.get("error"), ErrorDominio)
    assert resultado["error"].codigo == "ULTIMO_COORDINADOR"


@pytest.mark.commit_real
def test_baja_no_le_quita_el_horario_a_quien_lo_recibio_mientras_esperaba(fabrica_sesiones):
    with fabrica_sesiones() as s:
        carlos = crear_usuario(s, "Carlos Lugones")
        paula = crear_usuario(s, "Paula Méndez")
        enzo = crear_usuario(s, "Enzo", rol=RolUsuario.COORDINADOR)
        horario_id = crear_horario_de_prueba(s, carlos.id).id
        s.commit()
        carlos_id, paula_id, coordinador_id = carlos.id, paula.id, enzo.id

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        # designa a Paula
        abrir_version(s1, horario_id, {"medico_id": paula_id}, date(2026, 10, 13), HOY, AHORA, ZONA)

        def baja_de_carlos():
            resultado = dar_de_baja(s2, carlos_id, date(2026, 10, 19), s2.get(Usuario, coordinador_id), RELOJ)
            s2.commit()
            return resultado

        resultado = bloqueado_hasta_commit(s1, baja_de_carlos)

    assert "error" not in resultado, resultado.get("error")
    assert resultado["valor"].horarios_sin_titular == []
    with fabrica_sesiones() as s:
        versiones = s.scalars(
            select(VersionHorario).where(VersionHorario.horario_id == horario_id).order_by(VersionHorario.vigente_desde)
        ).all()
        assert [(v.medico_id, v.vigente_desde, v.vigente_hasta) for v in versiones] == [
            (carlos_id, date(2026, 9, 7), date(2026, 10, 13)),
            (paula_id, date(2026, 10, 13), None),
        ]


@pytest.mark.commit_real
def test_activar_y_promover_bloquea_a_los_coordinadores_antes_que_al_usuario(cliente, fabrica_sesiones, reloj):
    """Orden de bloqueos (backend/CLAUDE.md, convención 11): si el PATCH tomara primero al usuario y después a
    los coordinadores de id menor, otro cambio de rol sobre el mismo usuario cerraría un ciclo (deadlock)."""
    with fabrica_sesiones() as s:
        enzo = crear_usuario(s, "Enzo", rol=RolUsuario.COORDINADOR)
        nuevo = crear_usuario(s, "Nueva coordinadora", estado=EstadoUsuario.PENDIENTE)
        s.commit()
        enzo_id, nuevo_id, cabecera = enzo.id, nuevo.id, encabezados(enzo)

    with fabrica_sesiones() as retiene, fabrica_sesiones() as sonda:
        retiene.scalar(select(Usuario).where(Usuario.id == enzo_id).with_for_update())

        def promover():
            return cliente.patch(
                f"/api/usuarios/{nuevo_id}", json={"estado": "ACTIVO", "rol": "COORDINADOR"}, headers=cabecera
            )

        def usuario_libre_mientras_espera():
            try:
                sonda.scalar(select(Usuario).where(Usuario.id == nuevo_id).with_for_update(nowait=True))
            except OperationalError as exc:
                assert isinstance(exc.orig, LockNotAvailable)
                return False
            finally:
                sonda.rollback()
            return True

        estado = {}
        resultado = bloqueado_hasta_commit(retiene, promover, antes_de_confirmar=lambda: estado.update(libre=usuario_libre_mientras_espera()))

    assert estado["libre"], "el PATCH tomó al usuario antes que a los coordinadores"
    assert resultado["valor"].status_code == 200

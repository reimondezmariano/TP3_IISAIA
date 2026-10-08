from datetime import date, time

import pytest

from app.errores import ErrorDominio
from app.modelos import RolUsuario
from app.servicios.plantilla import abrir_version
from app.servicios.usuarios import cambiar_rol
from fabricas import HOY, bloqueado_hasta_commit, crear_horario_de_prueba, crear_usuario


@pytest.mark.commit_real
def test_dos_cambios_simultaneos_desde_la_misma_fecha(fabrica_sesiones):
    with fabrica_sesiones() as s:
        horario_id = crear_horario_de_prueba(s, None).id
        s.commit()

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        abrir_version(s1, horario_id, {"hora_inicio": time(9)}, date(2026, 10, 20), HOY)
        resultado = bloqueado_hasta_commit(
            s1, lambda: abrir_version(s2, horario_id, {"hora_inicio": time(10)}, date(2026, 10, 20), HOY)
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
        cambiar_rol(s1, beto_id, RolUsuario.MEDICO, HOY)  # Ana le quita el rol a Beto
        resultado = bloqueado_hasta_commit(s1, lambda: cambiar_rol(s2, ana_id, RolUsuario.MEDICO, HOY))

    assert isinstance(resultado.get("error"), ErrorDominio)
    assert resultado["error"].codigo == "ULTIMO_COORDINADOR"

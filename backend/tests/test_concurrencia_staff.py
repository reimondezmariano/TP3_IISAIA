from datetime import date, time

import pytest

from app.errores import ErrorDominio
from app.servicios.plantilla import abrir_version
from fabricas import HOY, bloqueado_hasta_commit, crear_horario_de_prueba


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

from datetime import date

import pytest

from app.dominio.plantilla import (
    EstadoHorario,
    Vigencia,
    estado_horario,
    hay_version_posterior,
    lunes_de,
    validar_desde,
    validar_fecha_ancla,
    version_a_modificar,
    version_que_cubre,
)
from app.errores import ErrorDominio

HOY = date(2026, 10, 12)


def v(version_id, desde, hasta=None, medico_id=1) -> Vigencia:
    return Vigencia(version_id=version_id, medico_id=medico_id, vigente_desde=desde, vigente_hasta=hasta)


def error_de(funcion, *args) -> tuple[str, int]:
    with pytest.raises(ErrorDominio) as excinfo:
        funcion(*args)
    return excinfo.value.codigo, excinfo.value.status


def test_lunes_de():
    assert lunes_de(date(2026, 10, 18)) == date(2026, 10, 12)  # domingo
    assert lunes_de(date(2026, 10, 12)) == date(2026, 10, 12)


def test_fecha_ancla_tiene_que_ser_lunes():
    validar_fecha_ancla(date(2026, 10, 12))
    assert error_de(validar_fecha_ancla, date(2026, 10, 13)) == ("FECHA_ANCLA_NO_LUNES", 422)


def test_desde_hoy_se_acepta_y_ayer_no():
    validar_desde(HOY, HOY)
    assert error_de(validar_desde, date(2026, 10, 11), HOY) == ("FECHA_PASADA", 422)


def test_version_que_cubre_devuelve_la_que_rige_ese_dia():
    versiones = [v(1, date(2026, 9, 7), date(2026, 11, 2)), v(2, date(2026, 11, 2))]
    assert version_que_cubre(versiones, date(2026, 10, 20), 7).version_id == 1
    assert version_que_cubre(versiones, date(2026, 11, 9), 7).version_id == 2


def test_version_que_empieza_ese_dia_no_se_parte():
    versiones = [v(1, date(2026, 9, 7), date(2026, 11, 2)), v(2, date(2026, 11, 2))]
    assert error_de(version_que_cubre, versiones, date(2026, 11, 2), 7) == ("VERSION_EN_ESA_FECHA", 409)


@pytest.mark.parametrize("desde", [date(2026, 10, 20), date(2026, 11, 2)])
def test_horario_cerrado_no_tiene_version_que_partir(desde):
    versiones = [v(1, date(2026, 9, 7), date(2026, 10, 20))]
    assert error_de(version_que_cubre, versiones, desde, 7) == ("HORARIO_SIN_VIGENCIA", 409)


def test_horario_que_todavia_no_empezo_no_tiene_version_que_partir():
    versiones = [v(1, date(2026, 11, 2))]
    assert error_de(version_que_cubre, versiones, date(2026, 10, 20), 7) == ("HORARIO_SIN_VIGENCIA", 409)


def test_hay_version_posterior():
    versiones = [v(1, date(2026, 9, 7), date(2026, 11, 2)), v(2, date(2026, 11, 2))]
    assert hay_version_posterior(versiones, date(2026, 10, 20))
    assert not hay_version_posterior(versiones, date(2026, 11, 9))


@pytest.mark.parametrize(
    "versiones,esperado",
    [
        ([v(1, date(2026, 9, 7))], EstadoHorario.CON_TITULAR),
        # La baja rige desde mañana: hoy todavía tiene titular.
        ([v(1, date(2026, 9, 7), date(2026, 10, 13)), v(2, date(2026, 10, 13), medico_id=None)], EstadoHorario.CON_TITULAR),
        ([v(1, date(2026, 9, 7), HOY), v(2, HOY, medico_id=None)], EstadoHorario.SIN_TITULAR),
        ([v(1, date(2026, 9, 7), HOY)], EstadoHorario.CERRADO),
        # Todavía no empezó: cuenta la próxima versión.
        ([v(1, date(2026, 11, 2))], EstadoHorario.CON_TITULAR),
        ([v(1, date(2026, 11, 2), medico_id=None)], EstadoHorario.SIN_TITULAR),
    ],
)
def test_estado_horario(versiones, esperado):
    assert estado_horario(versiones, HOY) == esperado


def test_version_que_todavia_no_rige_se_modifica_en_el_lugar():
    versiones = [v(1, date(2026, 9, 7), date(2026, 11, 2)), v(2, date(2026, 11, 2))]
    assert version_a_modificar(versiones, date(2026, 11, 2), 7, HOY) == (versiones[1], True)


def test_en_otra_fecha_se_parte_la_version_que_rige():
    versiones = [v(1, date(2026, 9, 7), date(2026, 11, 2)), v(2, date(2026, 11, 2))]
    assert version_a_modificar(versiones, date(2026, 10, 20), 7, HOY) == (versiones[0], False)


def test_version_que_ya_rige_hoy_no_se_modifica_en_el_lugar():
    # Empieza hoy: ya rige y puede tener turnos de hoy calculados con ella.
    versiones = [v(1, date(2026, 9, 7), HOY), v(2, HOY)]
    assert error_de(version_a_modificar, versiones, HOY, 7, HOY) == ("VERSION_EN_ESA_FECHA", 409)

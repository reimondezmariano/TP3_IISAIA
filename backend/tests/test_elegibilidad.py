from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.dominio.elegibilidad import Guardia, Motivo, es_elegible, motivo_inelegibilidad

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
INICIO = datetime(2026, 10, 17, 8, tzinfo=ZONA)
FIN = datetime(2026, 10, 17, 20, tzinfo=ZONA)
TITULAR = 1
MEDICO = 2


def guardia(dia_ini, hora_ini, dia_fin, hora_fin, min_fin=0):
    return Guardia(
        datetime(2026, 10, dia_ini, hora_ini, tzinfo=ZONA),
        datetime(2026, 10, dia_fin, hora_fin, min_fin, tzinfo=ZONA),
    )


def motivo(guardias=(), medico=MEDICO, titular=TITULAR):
    return motivo_inelegibilidad(medico, titular, INICIO, FIN, guardias)


def test_medico_libre_es_elegible():
    assert motivo() is None


def test_titular_no_se_postula_a_su_propio_turno():
    assert motivo(medico=TITULAR) is Motivo.ES_TITULAR


def test_turno_sin_titular_no_impide_a_nadie():
    assert motivo(titular=None) is None


def test_guardia_que_se_superpone_parcialmente_impide():
    assert motivo([guardia(17, 6, 17, 10)]) is Motivo.GUARDIA_SUPERPUESTA


def test_guardia_contenida_en_el_turno_impide():
    assert motivo([guardia(17, 10, 17, 12)]) is Motivo.GUARDIA_SUPERPUESTA


def test_guardia_que_contiene_al_turno_impide():
    assert motivo([guardia(17, 0, 17, 23, 59)]) is Motivo.GUARDIA_SUPERPUESTA


def test_guardia_que_termina_cuando_empieza_el_turno_no_impide():
    assert motivo([guardia(17, 0, 17, 8)]) is None


def test_guardia_que_empieza_cuando_termina_el_turno_no_impide():
    assert motivo([guardia(17, 20, 17, 23)]) is None


def test_guardia_que_cruza_medianoche_impide():
    assert motivo([guardia(16, 22, 17, 9)]) is Motivo.GUARDIA_SUPERPUESTA


def test_titular_y_superpuesta_informa_titular():
    assert motivo([guardia(17, 6, 17, 10)], medico=TITULAR) is Motivo.ES_TITULAR


def test_al_desaparecer_el_impedimento_vuelve_a_ser_elegible():
    ocupada = [guardia(17, 6, 17, 10)]
    assert motivo(ocupada) is Motivo.GUARDIA_SUPERPUESTA
    assert motivo([]) is None


def test_es_elegible_refleja_el_motivo():
    assert es_elegible(MEDICO, TITULAR, INICIO, FIN, []) is True
    assert es_elegible(TITULAR, TITULAR, INICIO, FIN, []) is False
    assert es_elegible(MEDICO, TITULAR, INICIO, FIN, [guardia(17, 6, 17, 10)]) is False


def test_instante_sin_zona_es_error():
    with pytest.raises(ValueError):
        motivo_inelegibilidad(MEDICO, TITULAR, datetime(2026, 10, 17, 8), FIN, [])
    with pytest.raises(ValueError):
        motivo([Guardia(datetime(2026, 10, 17, 6), datetime(2026, 10, 17, 10))])


def test_titular_con_guardia_sin_zona_tambien_es_error():
    with pytest.raises(ValueError):
        motivo([Guardia(datetime(2026, 10, 17, 6), datetime(2026, 10, 17, 10))], medico=TITULAR)


def test_superposicion_temprana_no_saltea_la_validacion_de_las_demas_guardias():
    sin_zona = Guardia(datetime(2026, 10, 1, 6), datetime(2026, 10, 1, 10))
    with pytest.raises(ValueError):
        motivo([guardia(17, 6, 17, 10), sin_zona])

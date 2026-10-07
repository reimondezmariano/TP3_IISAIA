from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.dominio.vacantes import es_urgente

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
INICIO = datetime(2026, 10, 17, 8, tzinfo=ZONA)


def test_con_mas_de_24_horas_no_es_urgente():
    assert es_urgente(INICIO, INICIO - timedelta(hours=24, minutes=1)) is False


def test_a_exactamente_24_horas_no_es_urgente():
    assert es_urgente(INICIO, INICIO - timedelta(hours=24)) is False


def test_con_menos_de_24_horas_es_urgente():
    assert es_urgente(INICIO, INICIO - timedelta(hours=23, minutes=59)) is True


def test_generada_con_el_turno_en_curso_es_urgente():
    assert es_urgente(INICIO, INICIO + timedelta(hours=1)) is True


def test_instante_sin_zona_es_error():
    with pytest.raises(ValueError):
        es_urgente(INICIO, datetime(2026, 10, 16, 9))

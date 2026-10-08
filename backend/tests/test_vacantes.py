from datetime import datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo

import pytest

from app.dominio.vacantes import asignado_a_restaurar, es_urgente, puede_generar, puede_retirar

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


def test_tzinfo_sin_desplazamiento_se_trata_como_sin_zona():
    class SinDesplazamiento(tzinfo):
        def utcoffset(self, dt):
            return None

        def dst(self, dt):
            return None

        def tzname(self, dt):
            return None

    with pytest.raises(ValueError):
        es_urgente(INICIO, datetime(2026, 10, 16, 9, tzinfo=SinDesplazamiento()))


# --- permisos (D15) ---


def test_el_titular_puede_generar():
    assert puede_generar(actor_id=1, es_coordinador=False, titular_id=1, asignado_id=None) is True


def test_el_asignado_puede_generar():
    assert puede_generar(actor_id=2, es_coordinador=False, titular_id=1, asignado_id=2) is True


def test_un_tercero_medico_no_puede_generar():
    assert puede_generar(actor_id=3, es_coordinador=False, titular_id=1, asignado_id=2) is False


def test_un_coordinador_siempre_puede_generar():
    assert puede_generar(actor_id=9, es_coordinador=True, titular_id=1, asignado_id=2) is True


def test_sin_titular_ni_asignado_solo_el_coordinador_puede_generar():
    assert puede_generar(actor_id=3, es_coordinador=False, titular_id=None, asignado_id=None) is False
    assert puede_generar(actor_id=9, es_coordinador=True, titular_id=None, asignado_id=None) is True


def test_retira_quien_la_genero_y_el_coordinador_no_un_tercero():
    assert puede_retirar(actor_id=1, es_coordinador=False, generada_por_id=1) is True
    assert puede_retirar(actor_id=9, es_coordinador=True, generada_por_id=1) is True
    assert puede_retirar(actor_id=3, es_coordinador=False, generada_por_id=1) is False


def test_se_restaura_solo_al_asignado_que_genero_la_vacante():
    assert asignado_a_restaurar(generada_por_id=5, asignado_anterior_id=5) == 5
    assert asignado_a_restaurar(generada_por_id=5, asignado_anterior_id=6) is None
    assert asignado_a_restaurar(generada_por_id=5, asignado_anterior_id=None) is None

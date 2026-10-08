from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.dominio.alertas import Umbral, alertas_pendientes

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
INICIO = datetime(2026, 10, 17, 8, tzinfo=ZONA)
FIN = INICIO + timedelta(hours=12)
ABIERTA = INICIO - timedelta(days=10)


def pendientes(ahora, enviadas=(), abierta=ABIERTA):
    return alertas_pendientes(INICIO, FIN, abierta, ahora, enviadas)


def test_antes_de_48_horas_no_hay_alertas():
    assert pendientes(INICIO - timedelta(hours=48, minutes=1)) == []


def test_a_las_48_horas_exactas_dispara_la_primera():
    assert pendientes(INICIO - timedelta(hours=48)) == [Umbral.HORAS_48]


def test_a_las_24_horas_con_la_primera_enviada_dispara_solo_la_segunda():
    assert pendientes(INICIO - timedelta(hours=24), {Umbral.HORAS_48}) == [Umbral.HORAS_24]


def test_al_inicio_dispara_la_tercera():
    assert pendientes(INICIO, {Umbral.HORAS_48, Umbral.HORAS_24}) == [Umbral.INICIO]


def test_sin_enviadas_y_ya_en_el_inicio_devuelve_los_tres_en_orden():
    assert pendientes(INICIO) == [Umbral.HORAS_48, Umbral.HORAS_24, Umbral.INICIO]


def test_no_repite_un_umbral_ya_enviado():
    assert pendientes(INICIO, set(Umbral)) == []


def test_vacante_abierta_a_10_horas_solo_dispara_el_inicio():
    assert pendientes(INICIO, abierta=INICIO - timedelta(hours=10)) == [Umbral.INICIO]


def test_vacante_abierta_justo_en_el_umbral_lo_incluye():
    ahora = INICIO - timedelta(hours=24)
    assert pendientes(ahora, abierta=ahora) == [Umbral.HORAS_24]


def test_turno_terminado_no_alerta():
    assert pendientes(FIN) == []


def test_instante_sin_zona_es_error():
    with pytest.raises(ValueError):
        pendientes(datetime(2026, 10, 17, 8))


def test_los_valores_de_umbral_coinciden_con_la_restriccion_de_la_bitacora():
    # ck_evento_alerta_umbral (migración 0002) solo admite estos valores en datos->>'umbral'.
    assert [u.value for u in Umbral] == ["48H", "24H", "INICIO"]

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.reloj import RelojFijo, RelojSistema, hoy

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def test_reloj_fijo_devuelve_el_instante_dado():
    instante = datetime(2026, 10, 12, 9, 0, tzinfo=ZONA)
    assert RelojFijo(instante).ahora() == instante


def test_reloj_fijo_avanza():
    reloj = RelojFijo(datetime(2026, 10, 12, 9, 0, tzinfo=ZONA))
    reloj.avanzar(timedelta(hours=26))
    assert reloj.ahora() == datetime(2026, 10, 13, 11, 0, tzinfo=ZONA)


def test_reloj_fijo_rechaza_instante_sin_zona():
    with pytest.raises(ValueError):
        RelojFijo(datetime(2026, 10, 12, 9, 0))


def test_reloj_sistema_devuelve_hora_con_zona_del_servicio():
    ahora = RelojSistema(ZONA).ahora()
    assert ahora.tzinfo is not None
    assert ahora.utcoffset() == timedelta(hours=-3)


def test_hoy_usa_la_zona_del_servicio():
    # 01:30 UTC del 13/10 son las 22:30 del 12/10 en Buenos Aires.
    assert hoy(RelojFijo(datetime(2026, 10, 13, 1, 30, tzinfo=UTC))) == date(2026, 10, 12)

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.reloj import RelojFijo, RelojSistema

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

from dataclasses import replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.dominio.consolidacion import Consolidacion, TurnoConsolidable, consolidar, realizador_presunto

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
FIN = datetime(2026, 10, 17, 20, tzinfo=ZONA)
AHORA = FIN + timedelta(minutes=5)


def turno(turno_id=1, fin=FIN, titular=1, asignado=None, vacante=False, sin_cobertura=False, consolidado_en=None):
    return TurnoConsolidable(turno_id, fin, titular, asignado, vacante, sin_cobertura, consolidado_en)


def test_turno_terminado_lo_hace_el_titular():
    assert consolidar([turno()], AHORA) == [Consolidacion(1, 1, AHORA)]


def test_turno_cubierto_lo_hace_el_asignado():
    assert consolidar([turno(asignado=2)], AHORA)[0].realizador_id == 2


def test_vacante_abierta_sin_asignado_queda_sin_realizador():
    assert consolidar([turno(vacante=True)], AHORA)[0].realizador_id is None


def test_sin_cobertura_queda_sin_realizador_aunque_haya_titular():
    assert consolidar([turno(sin_cobertura=True)], AHORA)[0].realizador_id is None


def test_turno_sin_titular_y_sin_asignado_queda_sin_realizador():
    assert consolidar([turno(titular=None)], AHORA)[0].realizador_id is None


def test_turno_sin_titular_cubierto_lo_hace_el_asignado():
    assert consolidar([turno(titular=None, asignado=3)], AHORA)[0].realizador_id == 3


def test_realizador_presunto_directo():
    assert realizador_presunto(1, None, False, False) == 1
    assert realizador_presunto(1, 2, True, False) == 2
    assert realizador_presunto(1, 2, False, True) is None


def test_turno_en_curso_no_se_consolida():
    assert consolidar([turno()], FIN - timedelta(minutes=1)) == []


def test_turno_que_termina_justo_ahora_se_consolida():
    assert consolidar([turno()], FIN) == [Consolidacion(1, 1, FIN)]


def test_ya_consolidado_no_se_repite():
    pendientes = [turno(1), turno(2, asignado=3)]
    primera = consolidar(pendientes, AHORA)
    assert len(primera) == 2
    reflejados = [replace(t, consolidado_en=c.consolidado_en) for t, c in zip(pendientes, primera)]
    assert consolidar(reflejados, AHORA + timedelta(hours=1)) == []


def test_turno_rectificado_no_se_vuelve_a_consolidar():
    rectificado = turno(asignado=4, consolidado_en=AHORA - timedelta(hours=1))
    assert consolidar([rectificado], AHORA) == []


def test_consolida_varios_y_deja_los_pendientes():
    turnos = [
        turno(1),
        turno(2, fin=AHORA + timedelta(hours=3)),
        turno(3, consolidado_en=AHORA - timedelta(days=1)),
        turno(4, asignado=2),
    ]
    assert [c.turno_id for c in consolidar(turnos, AHORA)] == [1, 4]


def test_instante_sin_zona_es_error():
    with pytest.raises(ValueError):
        consolidar([turno()], datetime(2026, 10, 17, 21))
    with pytest.raises(ValueError):
        consolidar([turno(fin=datetime(2026, 10, 17, 20))], AHORA)

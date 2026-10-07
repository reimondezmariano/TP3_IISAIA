from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.dominio.elegibilidad import Guardia
from app.dominio.equidad import Candidato, TurnoDelMes, contar_coberturas, horas_en_semana, ordenar_candidatos

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
T0 = datetime(2026, 10, 10, 12, tzinfo=ZONA)


def cand(medico_id, minutos=0):
    return Candidato(medico_id, T0 + timedelta(minutes=minutos))


def ids(candidatos):
    return [c.medico_id for c in candidatos]


def turno(mes, dia, hora=8, asignado=2, titular=1, anio=2026):
    return TurnoDelMes(datetime(anio, mes, dia, hora, tzinfo=ZONA), asignado, titular)


# --- ordenar_candidatos (D17) ---


def test_gana_quien_cubrio_menos():
    assert ids(ordenar_candidatos([cand(1), cand(2), cand(3)], {1: 3, 2: 1, 3: 2})) == [2, 3, 1]


def test_la_equidad_manda_sobre_la_hora_de_postulacion():
    ordenados = ordenar_candidatos([cand(1, 0), cand(2, 60)], {1: 2, 2: 0})
    assert ids(ordenados) == [2, 1]


def test_desempata_por_hora_de_postulacion():
    ordenados = ordenar_candidatos([cand(1, 30), cand(2, 10), cand(3, 20)], {1: 1, 2: 1, 3: 1})
    assert ids(ordenados) == [2, 3, 1]


def test_medico_ausente_del_mapa_cuenta_cero():
    assert ids(ordenar_candidatos([cand(1), cand(2)], {1: 1})) == [2, 1]


def test_empate_total_se_ordena_por_medico_id():
    assert ids(ordenar_candidatos([cand(3), cand(1), cand(2)], {})) == [1, 2, 3]


def test_lista_vacia_devuelve_lista_vacia():
    assert ordenar_candidatos([], {}) == []


def test_no_modifica_la_entrada():
    entrada = [cand(2), cand(1)]
    ordenar_candidatos(entrada, {2: 5})
    assert ids(entrada) == [2, 1]


# --- contar_coberturas (D17) ---


def test_cuenta_cobertura_si_asignado_no_es_titular():
    assert contar_coberturas([turno(10, 5)], 2026, 10, ZONA) == {2: 1}


def test_no_cuenta_el_turno_que_hace_su_titular():
    assert contar_coberturas([turno(10, 5, asignado=1, titular=1)], 2026, 10, ZONA) == {}


def test_no_cuenta_turno_sin_asignado():
    assert contar_coberturas([turno(10, 5, asignado=None)], 2026, 10, ZONA) == {}


def test_cuenta_cobertura_de_turno_sin_titular():
    assert contar_coberturas([turno(10, 5, titular=None)], 2026, 10, ZONA) == {2: 1}


def test_solo_cuenta_el_mes_pedido():
    turnos = [turno(9, 30), turno(10, 5), turno(11, 2)]
    assert contar_coberturas(turnos, 2026, 10, ZONA) == {2: 1}


def test_el_mes_se_mide_en_la_zona_del_servicio():
    # 31/10 22:00 -03:00 es 01/11 01:00 UTC: sigue siendo octubre para el servicio.
    en_octubre = TurnoDelMes(datetime(2026, 10, 31, 22, tzinfo=ZONA), 2, 1)
    en_noviembre = TurnoDelMes(datetime(2026, 11, 1, 0, 30, tzinfo=ZONA), 3, 1)
    assert contar_coberturas([en_octubre, en_noviembre], 2026, 10, ZONA) == {2: 1}
    assert contar_coberturas([en_octubre, en_noviembre], 2026, 11, ZONA) == {3: 1}


def test_acumula_varias_coberturas_del_mismo_medico():
    turnos = [turno(10, 5), turno(10, 12), turno(10, 19, asignado=3)]
    assert contar_coberturas(turnos, 2026, 10, ZONA) == {2: 2, 3: 1}


def test_instante_sin_zona_es_error():
    with pytest.raises(ValueError):
        ordenar_candidatos([Candidato(1, datetime(2026, 10, 10, 12))], {})
    with pytest.raises(ValueError):
        contar_coberturas([TurnoDelMes(datetime(2026, 10, 5, 8), 2, 1)], 2026, 10, ZONA)


# --- horas_en_semana (dato informativo de D17) ---
# Semana del lunes 12/10/2026 al domingo 18/10.


def g(dia_ini, hora_ini, dia_fin, hora_fin, mes_ini=10, mes_fin=10):
    return Guardia(
        datetime(2026, mes_ini, dia_ini, hora_ini, tzinfo=ZONA),
        datetime(2026, mes_fin, dia_fin, hora_fin, tzinfo=ZONA),
    )


def test_suma_las_guardias_de_la_semana():
    assert horas_en_semana([g(13, 8, 13, 16), g(15, 8, 15, 20)], date(2026, 10, 14), ZONA) == 20.0


def test_ignora_guardias_de_otra_semana():
    assert horas_en_semana([g(6, 8, 6, 16), g(20, 8, 20, 16)], date(2026, 10, 14), ZONA) == 0.0


def test_guardia_que_cruza_el_domingo_se_prorratea():
    cruza = g(18, 20, 19, 8)
    assert horas_en_semana([cruza], date(2026, 10, 14), ZONA) == 4.0
    assert horas_en_semana([cruza], date(2026, 10, 19), ZONA) == 8.0


def test_la_referencia_puede_ser_cualquier_dia_de_la_semana():
    guardias = [g(13, 8, 13, 16)]
    assert horas_en_semana(guardias, date(2026, 10, 12), ZONA) == horas_en_semana(guardias, date(2026, 10, 18), ZONA) == 8.0


def test_sin_guardias_son_cero_horas():
    assert horas_en_semana([], date(2026, 10, 14), ZONA) == 0.0


def test_horas_instante_sin_zona_es_error():
    with pytest.raises(ValueError):
        horas_en_semana([Guardia(datetime(2026, 10, 13, 8), datetime(2026, 10, 13, 16))], date(2026, 10, 14), ZONA)

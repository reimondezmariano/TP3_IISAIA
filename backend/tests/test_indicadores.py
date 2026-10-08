import pytest

from app.dominio.indicadores import meses_del_rango
from app.errores import ErrorDominio


def test_meses_del_rango_cruza_el_anio():
    assert meses_del_rango("2026-11", "2027-02") == ["2026-11", "2026-12", "2027-01", "2027-02"]


def test_un_solo_mes():
    assert meses_del_rango("2026-10", "2026-10") == ["2026-10"]


def test_hasta_anterior_es_rango_invalido():
    with pytest.raises(ErrorDominio) as error:
        meses_del_rango("2026-10", "2026-09")
    assert error.value.codigo == "RANGO_INVALIDO"


def test_mas_de_24_meses_es_demasiado():
    assert len(meses_del_rango("2025-01", "2026-12")) == 24
    with pytest.raises(ErrorDominio) as error:
        meses_del_rango("2025-01", "2027-01")
    assert error.value.codigo == "RANGO_DEMASIADO_GRANDE"

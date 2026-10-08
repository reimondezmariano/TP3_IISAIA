import pytest
from pydantic import ValidationError

from app.api import esquemas_operacion as esq
from app.api.esquemas_operacion import EJEMPLOS


@pytest.mark.parametrize("nombre", sorted(EJEMPLOS))
def test_cada_ejemplo_valida_contra_su_esquema(nombre):
    clase = getattr(esq, nombre)
    ejemplo = EJEMPLOS[nombre]
    assert isinstance(ejemplo, clase)
    assert clase.model_validate(ejemplo.model_dump(by_alias=True, mode="json")) == ejemplo


def test_hay_un_ejemplo_por_cada_respuesta_del_contrato():
    assert set(EJEMPLOS) == {
        "VacanteOut",
        "LoteVacantesOut",
        "PostulacionOut",
        "CandidatosOut",
        "AsignacionOut",
    }


def test_los_ejemplos_salen_en_camel_case():
    json = EJEMPLOS["VacanteOut"].model_dump_json(by_alias=True)
    assert '"turnoId"' in json and '"generadaPor"' in json and '"creadaEn"' in json


def test_instantes_de_ejemplo_llevan_desplazamiento():
    assert "-03:00" in EJEMPLOS["VacanteOut"].model_dump_json(by_alias=True)


def test_el_ejemplo_de_candidatos_incluye_un_no_elegible_sin_posicion():
    candidatos = EJEMPLOS["CandidatosOut"].candidatos
    assert [c.posicion for c in candidatos if c.elegible] == [1, 2]
    assert [c.posicion for c in candidatos if not c.elegible] == [None]
    assert all(c.motivo_inelegibilidad is not None for c in candidatos if not c.elegible)


def test_lote_rechaza_lista_vacia_y_mas_de_31():
    with pytest.raises(ValidationError):
        esq.LoteVacantesIn(turno_ids=[])
    with pytest.raises(ValidationError):
        esq.LoteVacantesIn(turno_ids=[f"7:2026-10-{d:02d}" for d in range(1, 32)] + ["7:2026-11-01"])
    assert len(esq.LoteVacantesIn(turno_ids=["7:2026-10-17"]).turno_ids) == 1


def test_asignar_acepta_camel_case_y_reasignar_es_falso_por_defecto():
    datos = esq.AsignarIn.model_validate({"medicoId": 3})
    assert datos.medico_id == 3 and datos.reasignar is False

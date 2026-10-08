from sqlalchemy import text

from app.modelos import EstadoConsolidacion
from fabricas import debe_fallar, guardar


def test_consolidacion_estado_tiene_rls(sesion):
    rls = sesion.execute(
        text("SELECT relrowsecurity FROM pg_class WHERE relname = 'consolidacion_estado'")
    ).scalar_one()
    assert rls is True


def test_consolidacion_estado_admite_una_sola_fila(sesion):
    guardar(sesion, EstadoConsolidacion(id=1, consolidado_hasta=None))
    debe_fallar(sesion, EstadoConsolidacion(id=2, consolidado_hasta=None), "ck_consolidacion_estado_unica")


def test_indice_de_turnos_sin_consolidar_es_parcial(sesion):
    definicion = sesion.execute(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_turno_sin_consolidar'")
    ).scalar_one()
    assert "WHERE (consolidado_en IS NULL)" in definicion

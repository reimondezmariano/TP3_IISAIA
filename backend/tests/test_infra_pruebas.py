import pytest
from sqlalchemy import text

from conftest import verificar_base_local


def test_verificar_base_local_acepta_localhost():
    verificar_base_local("postgresql+psycopg://guardia:guardia@localhost:5433/guardia_test")


def test_verificar_base_local_rechaza_la_base_de_desarrollo():
    with pytest.raises(RuntimeError, match="_test"):
        verificar_base_local("postgresql+psycopg://guardia:guardia@localhost:5433/guardia")


def test_verificar_base_local_rechaza_host_remoto():
    with pytest.raises(RuntimeError, match="pooler.supabase.com"):
        verificar_base_local("postgresql+psycopg://u:p@aws-0-sa-east-1.pooler.supabase.com:5432/postgres")


def test_sesion_apunta_a_la_base_de_prueba(sesion):
    assert sesion.execute(text("SELECT current_database()")).scalar_one() == "guardia_test"


def test_fabrica_sesiones_fuera_de_commit_real_falla(request):
    with pytest.raises(RuntimeError, match="commit_real"):
        request.getfixturevalue("fabrica_sesiones")

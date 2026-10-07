import pytest

from app.dominio.registro import es_codigo_de_coordinacion


@pytest.mark.parametrize(
    "ingresado,configurado,esperado",
    [
        ("SMG", "SMG", True),
        (" smg ", "SMG", True),
        ("SMG", " smg ", True),
        ("SMX", "SMG", False),
        ("SMGX", "SMG", False),
        ("", "SMG", False),
        ("", "", False),
        ("   ", "   ", False),
        ("SMG", "", False),
    ],
)
def test_es_codigo_de_coordinacion(ingresado, configurado, esperado):
    assert es_codigo_de_coordinacion(ingresado, configurado) is esperado

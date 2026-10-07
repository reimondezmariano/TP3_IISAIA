"""Registro con código de coordinación (D30)."""

import hmac


def es_codigo_de_coordinacion(ingresado: str, configurado: str) -> bool:
    """Compara sin distinguir mayúsculas ni espacios en los extremos, en tiempo constante.

    Sin código configurado en el servidor, ningún código es válido: nadie se registra como coordinador.
    """
    esperado = configurado.strip().upper()
    if not esperado:
        return False
    return hmac.compare_digest(ingresado.strip().upper().encode(), esperado.encode())

class ErrorDominio(Exception):
    """Error con código legible por la interfaz. Se responde como {"codigo", "mensaje"}."""

    def __init__(self, codigo: str, mensaje: str, status: int = 422) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.status = status

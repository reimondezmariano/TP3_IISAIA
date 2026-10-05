from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errores import ErrorDominio

_CODIGOS_HTTP = {401: "SIN_SESION", 403: "SIN_PERMISO", 404: "NO_ENCONTRADO", 405: "METODO_NO_PERMITIDO"}


def _respuesta(status: int, codigo: str, mensaje: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"codigo": codigo, "mensaje": mensaje})


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorDominio)
    async def _error_dominio(_: Request, exc: ErrorDominio) -> JSONResponse:
        return _respuesta(exc.status, exc.codigo, exc.mensaje)

    @app.exception_handler(RequestValidationError)
    async def _error_validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
        detalle = "; ".join(
            f"{'.'.join(str(parte) for parte in error['loc'])}: {error['msg']}" for error in exc.errors()
        )
        return _respuesta(422, "VALIDACION", detalle)

    @app.exception_handler(StarletteHTTPException)
    async def _error_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        codigo = _CODIGOS_HTTP.get(exc.status_code, f"HTTP_{exc.status_code}")
        return _respuesta(exc.status_code, codigo, str(exc.detail))

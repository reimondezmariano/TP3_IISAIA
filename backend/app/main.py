from fastapi import APIRouter, FastAPI

from app.api import health, sesion, turnos
from app.api.manejadores import registrar_manejadores


def crear_app() -> FastAPI:
    app = FastAPI(title="Guardia Viva", version="0.1.0")
    registrar_manejadores(app)

    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(sesion.router)
    api.include_router(turnos.router)
    app.include_router(api)
    return app


app = crear_app()

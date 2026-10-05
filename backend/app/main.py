from fastapi import APIRouter, FastAPI

from app.api.manejadores import registrar_manejadores


def crear_app() -> FastAPI:
    app = FastAPI(title="Guardia Viva", version="0.1.0")
    registrar_manejadores(app)

    api = APIRouter(prefix="/api")
    app.include_router(api)
    return app


app = crear_app()

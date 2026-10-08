from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import (
    asignacion,
    coordinacion,
    demo,
    health,
    horarios,
    notificaciones,
    postulaciones,
    sesion,
    turnos,
    usuarios,
    vacantes,
)
from app.api.manejadores import registrar_manejadores

# D05: en producción el backend sirve la compilación del frontend (un solo despliegue).
CARPETA_FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def crear_app(carpeta_frontend: Path | None = None) -> FastAPI:
    app = FastAPI(title="Guardia Viva", version="0.1.0")
    registrar_manejadores(app)

    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(sesion.router)
    api.include_router(turnos.router)
    api.include_router(usuarios.router)
    api.include_router(horarios.router)
    api.include_router(vacantes.router)
    api.include_router(postulaciones.router)
    api.include_router(asignacion.router)
    api.include_router(coordinacion.router)
    api.include_router(notificaciones.router)
    api.include_router(demo.router)
    app.include_router(api)
    carpeta = CARPETA_FRONTEND if carpeta_frontend is None else carpeta_frontend
    if carpeta.is_dir():
        # Después de /api: lo que no existe bajo /api responde 404 con formato, no la página del frontend.
        app.mount("/", StaticFiles(directory=carpeta, html=True), name="frontend")
    return app


app = crear_app()

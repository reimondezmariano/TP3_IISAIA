from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.errores import ErrorDominio
from app.reloj import Reloj, get_reloj

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db), reloj: Reloj = Depends(get_reloj)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise ErrorDominio("BASE_NO_DISPONIBLE", "No se pudo conectar con la base de datos.", 503) from exc
    return {"estado": "ok", "base": "ok", "ahora": reloj.ahora().isoformat()}

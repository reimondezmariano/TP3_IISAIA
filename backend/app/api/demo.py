from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import requiere_coordinador
from app.config import Settings, get_settings
from app.db import get_db
from app.errores import ErrorDominio
from app.modelos import Usuario
from app.reloj import Reloj, get_reloj_sistema
from app.repos.consolidacion import desfase_demo, guardar_desfase_demo, hay_historia_despues

router = APIRouter()


class RelojIn(Esquema):
    ahora: AwareDatetime | None


class RelojOut(Esquema):
    ahora: datetime
    desfase_horas: float


def exigir_modo_demo(settings: Settings = Depends(get_settings)) -> None:
    """D27: el reloj de demo no existe fuera del modo demo."""
    if not settings.modo_demo:
        raise ErrorDominio("NO_ENCONTRADO", "Not Found", 404)


@router.post(
    "/demo/reloj",
    response_model=RelojOut,
    dependencies=[Depends(exigir_modo_demo)],
    include_in_schema=get_settings().modo_demo,
)
def mover_reloj(
    datos: RelojIn,
    db: Session = Depends(get_db),
    sistema: Reloj = Depends(get_reloj_sistema),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> RelojOut:
    """Adelanta el reloj de demo para mostrar consolidación y alertas (D27).

    Nunca va hacia atrás sobre historia ya registrada: un turno consolidado quedaría en el futuro. `null` vuelve
    a la hora real solo si no se registró nada con el reloj adelantado; si no, hay que reiniciar la demo
    (`scripts.seed`), que también vuelve a la hora real.
    """
    zona = get_settings().zona
    real = sistema.ahora()
    if datos.ahora is None:
        if hay_historia_despues(db, real, real.astimezone(zona).date()):
            raise ErrorDominio(
                "REINICIAR_DEMO",
                "Ya se registró historia con el reloj adelantado: para volver a la hora real, reiniciá la demo.",
                409,
            )
        desfase = timedelta(0)
    else:
        if datos.ahora < real + desfase_demo(db):
            raise ErrorDominio("RELOJ_HACIA_ATRAS", "El reloj de demo solo puede avanzar.")
        desfase = datos.ahora - real
    guardar_desfase_demo(db, desfase)
    db.commit()
    return RelojOut(ahora=(real + desfase).astimezone(zona), desfase_horas=round(desfase.total_seconds() / 3600, 2))

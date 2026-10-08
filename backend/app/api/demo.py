from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime

from app.api.esquemas import Esquema
from app.auth import requiere_coordinador
from app.config import Settings, get_settings
from app.errores import ErrorDominio
from app.modelos import Usuario
from app.reloj import Reloj, desfase_demo, fijar_desfase_demo, get_reloj_sistema

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
    sistema: Reloj = Depends(get_reloj_sistema),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> RelojOut:
    """Adelanta el reloj de demo para mostrar consolidación y alertas (D27). `null` vuelve a la hora real.

    Solo avanza: volver atrás dejaría turnos ya consolidados en el futuro.
    """
    real = sistema.ahora()
    if datos.ahora is None:
        fijar_desfase_demo(timedelta(0))
    else:
        if datos.ahora < real + desfase_demo():
            raise ErrorDominio("RELOJ_HACIA_ATRAS", "El reloj de demo solo puede avanzar.")
        fijar_desfase_demo(datos.ahora - real)
    desfase = desfase_demo()
    zona = get_settings().zona
    return RelojOut(ahora=(real + desfase).astimezone(zona), desfase_horas=round(desfase.total_seconds() / 3600, 2))

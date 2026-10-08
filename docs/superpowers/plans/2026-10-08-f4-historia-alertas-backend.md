# F4: historia y alertas (backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que el backend guarde la historia de las guardias sin un proceso programado (consolidación perezosa), avise a los coordinadores cuando una vacante sigue abierta (alertas a las 48 h, 24 h y al inicio), permita marcar un turno sin cobertura, mida las horas sin cobertura por mes, exponga las notificaciones y tenga un reloj de demo.

**Architecture:** las reglas puras ya están en `app/dominio/consolidacion.py` y `app/dominio/alertas.py` (Mariano, F3). Este plan agrega una tabla de una fila con la marca "consolidado hasta" (migración 0004), un servicio `ponerse_al_dia` que consolida y emite alertas dentro de la transacción de quien lo llama, y lo invoca antes de responder `GET /turnos`, `GET /notificaciones`, `GET /indicadores/sin-cobertura` y `POST /consolidacion`. Las notificaciones se crean con `app/servicios/notificaciones.notificar`, que también usará Mariano desde vacantes. El reloj de demo es un desfase en memoria sobre la hora del sistema, que solo existe con `MODO_DEMO=true`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic (SQL a mano), pytest contra Postgres 15 local (puerto 5433). Sin dependencias nuevas.

**Spec:** no hay spec propio. Las reglas salen de `docs/decisiones-arquitectura.md` (D05, D11, D19, D20, D22, D24, D27, D31), del CLAUDE.md de la raíz (endpoints y contrato) y de `backend/CLAUDE.md` (estructura y convenciones). Las "Decisiones de este plan" completan lo que esas decisiones dejan abierto.

**Branch:** `feature/f4-historia-alertas`, creada desde `main` (el PR #10 de F5 ya está mergeado).

## Global Constraints

- Todos los endpoints bajo `/api`; JSON en camelCase (esquemas que heredan de `app.api.esquemas.Esquema`); instantes en ISO 8601 con desplazamiento, convertidos a la zona del servicio antes de responder (`2026-10-17T08:00:00-03:00`).
- Errores con `ErrorDominio(codigo, mensaje, status)`: 401 sin sesión, 403 rol insuficiente, 404 inexistente, 409 conflicto de estado o concurrencia, 422 regla de negocio.
- Identificador de turno `"horarioId:fecha"` (D09) en toda respuesta; nunca el `turno.id` entero.
- Nada fuera de `app/reloj.py` consulta la hora del sistema (D27, regla 10). Los instantes de dominio (`consolidado_en`, `cerrada_en`, `sin_cobertura_en`, `ocurrido_en`, `creada_en`, `leida_en`) salen de `reloj.ahora()`.
- Toda acción de dominio escribe su `EventoTurno` y sus notificaciones en la misma transacción (D22, regla 5). La bitácora solo se agrega. La consolidación normal no escribe evento (D22).
- Concurrencia con restricciones y bloqueos de la base, no en memoria (regla 8). Orden de bloqueos: `usuario`, `horario_pactado`, `consolidacion_estado`, `turno`, `vacante`; varias filas del mismo tipo por id ascendente.
- Servicios y repos no hacen commit; lo hace el router.
- **No tocar** `app/api/operacion.py`, `app/api/esquemas_operacion.py` (PR #11 de Mariano), ni crear `app/repos/turnos.py`, `app/servicios/vacantes.py`, `app/servicios/postulaciones.py` o `app/api/vacantes.py`: son de Mariano. No modificar las funciones de `app/dominio/consolidacion.py` ni `app/dominio/alertas.py`.
- Migración nueva: `0004`, con `down_revision = "0003"`, SQL con `op.execute` y RLS activado en la tabla nueva (D07).
- Pruebas siempre contra Postgres: `docker compose up -d --wait` desde la raíz y `.venv/bin/pytest` desde `backend/`. Reloj de prueba: lunes 12/10/2026 09:00 (fixture `reloj`). Horario de prueba por defecto: martes 08:00 a 20:00 desde el 7/9, así que sus turnos terminados al 12/10 son 8/9, 15/9, 22/9, 29/9 y 6/10.
- Commits chicos, en español, citando la decisión. Un commit por tarea. Cada commit termina con la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Decisiones de este plan

Cada una con su costo si está mal; van a `docs/bitacora-de-desvios.md` al cerrar.

1. **Marca de consolidación** (tabla `consolidacion_estado`, una fila): los turnos calculados con fecha anterior a la marca ya se materializaron y consolidaron. Sin marca, cada consulta recalcularía todos los turnos desde la primera vigencia. La primera vez se parte de la primera `vigente_desde`. Es seguro porque ningún cambio de plantilla empieza antes de hoy (backend/CLAUDE.md, punto 12). Costo: si alguien carga una versión con vigencia pasada por SQL, esos turnos no se consolidan.
2. **La fila de la marca se bloquea** (`FOR UPDATE`) en cada consolidación: dos consultas simultáneas se esperan en lugar de duplicar trabajo. Costo: `GET /turnos` se serializa durante la consolidación (milisegundos con 12 usuarios).
3. **Consolidar con una vacante abierta la cierra como `SIN_COBERTURA`**, completa `sin_cobertura_en` y escribe `TURNO_SIN_COBERTURA` con actor sistema (`actor_id` NULL) y `datos = {"vacante_id", "al_consolidar": true}`. D19 dice que se consolida sin realizador; dejar la vacante abierta para siempre mostraría como abiertas vacantes de turnos pasados. Costo: un evento de sistema que D22 no lista para este caso.
4. **`POST /turnos/{id}/sin-cobertura` exige una vacante abierta y que el turno haya empezado** (D19: "si al llegar el inicio la vacante sigue abierta"). Antes del inicio responde 422 `TURNO_NO_EMPEZO`. Un turno BAJA sin vacante no se marca: si nadie lo cubre, la consolidación lo deja sin realizador y cuenta igual en el indicador (D24). No envía notificaciones: no hay a quién avisar algo nuevo.
5. **Alertas solo para turnos con vacante abierta** (D19 las define sobre la vacante). Los turnos BAJA sin vacante ya se ven en rojo (D24) y no generan alertas.
6. **Si vencieron varios umbrales a la vez** (servidor caído o reloj de demo adelantado), se registran todos los eventos `ALERTA_SIN_COBERTURA` (para que no se disparen después) y se manda **una sola** notificación, la del umbral más reciente. Costo: el evento de 48 h existe aunque nadie recibió ese aviso.
7. **Las alertas se evalúan en cada `GET /notificaciones`** (lo consulta cada usuario cada 10 a 15 s, D05) además de `GET /turnos`. Así llegan a tiempo sin proceso programado. El índice único `ux_evento_alerta_por_umbral` y el `INSERT ... ON CONFLICT DO NOTHING` garantizan una sola alerta por turno y umbral aunque dos pedidos lleguen juntos. `GET /notificaciones` no consolida (para no bloquear la marca en cada consulta periódica).
8. **Destinatarios "con acceso"**: ACTIVO, o BAJA hasta su `fecha_baja` inclusive (la misma regla que `usuario_actual`, D24). `destinatarios(...)` es la función que Mariano usará para `VACANTE_URGENTE`.
9. **Reloj de demo en memoria** (desfase en una variable del módulo `app/reloj.py`): un solo proceso de uvicorn en la demo. `POST /demo/reloj` con `{"ahora": instante}` solo avanza (422 `RELOJ_HACIA_ATRAS`), y `{"ahora": null}` vuelve a la hora real (pensado para usar después del seed). Solo coordinadores. Fuera de modo demo responde 404 y no aparece en `/docs`. Costo: reiniciar el servidor vuelve a la hora real; con varios procesos cada uno tendría su desfase.
10. **El indicador cuenta turnos consolidados sin realizador** (sin cobertura, vacante abierta al terminar y horarios BAJA sin cubrir), agrupados por el mes de su fecha de inicio (D13). Rango `desde`/`hasta` en `AAAA-MM`, hasta 24 meses, con meses en cero incluidos. Una rectificación que agregue realizador lo saca del indicador.
11. **Tipos de notificación**: `TipoNotificacion` en `app/dominio/notificaciones.py` con `VACANTE_URGENTE` (la usa Mariano) y `ALERTA_SIN_COBERTURA`. Quien necesite otro tipo lo agrega al enum; la columna sigue siendo texto (sin migración).
12. **Fuera de este plan:** rectificación (`POST /turnos/{id}/rectificacion`), `GET /turnos/{id}`, estado de los turnos dentro de `GET /turnos` y frontend. `GET /turnos` sigue devolviendo exactamente el mismo JSON.

## Coordinación con Mariano

- `notificar(sesion, usuario_ids, tipo, mensaje, ahora, turno=None, datos=None)` y `destinatarios(sesion, rol, dia, excepto=())` en `app/servicios/notificaciones.py` (Task 3). Avisarle cuando el PR esté mergeado.
- Asignar un turno marcado sin cobertura: `realizador_presunto` devuelve None si `sin_cobertura` es verdadero. Si su `PUT /asignacion` permite asignar después de marcar sin cobertura, tiene que limpiar `sin_cobertura_en` (o responder 409). Se le avisa en el PR.
- Ambos PR tocan `app/main.py` (una línea de `include_router` cada uno) y `backend/CLAUDE.md`: conflicto trivial.

## Review Focus

1. **Reinicio de la demo con la marca adelantada:** si el seed vacía usuarios y horarios pero no la marca, después de reiniciar nunca se consolidan los turnos anteriores a la marca vieja. El seed vacía `consolidacion_estado` (prueba en Task 1).
2. **Reloj de demo hacia atrás:** un turno ya consolidado quedaría "en el futuro". Solo se avanza; `null` vuelve a la hora real (prueba en Task 2).
3. **Reloj adelantado varios días con vacantes abiertas:** los coordinadores esperan un aviso por turno, no tres juntos (prueba en Task 5).
4. **Dos coordinadores consultando a la vez:** esperan una sola alerta por turno y umbral, no dos (prueba `commit_real` en Task 5), y una sola fila por turno consolidado (prueba `commit_real` en Task 4).
5. **Marcar como leída una notificación ajena:** responde 404 y no revela que existe (prueba en Task 7).

---

## File Structure

```
backend/migrations/versions/0004_consolidacion.py   (T1) tabla consolidacion_estado + índice de turnos sin consolidar
backend/app/modelos/consolidacion.py               (T1) EstadoConsolidacion
backend/app/modelos/turno.py                       (T1) índice ix_turno_sin_consolidar
backend/app/modelos/__init__.py                    (T1) exporta EstadoConsolidacion
backend/scripts/seed.py                            (T1) vacía también la marca
backend/app/reloj.py                               (T2) RelojDesplazado, desfase de demo, get_reloj_sistema
backend/app/api/demo.py                            (T2) POST /demo/reloj
backend/app/dominio/notificaciones.py              (T3) TipoNotificacion, mensaje_alerta
backend/app/servicios/notificaciones.py            (T3, T7) notificar, destinatarios, marcar_leida
backend/app/repos/consolidacion.py                 (T4) marca, inserción de consolidados, turnos guardados pendientes
backend/app/servicios/consolidacion.py             (T4, T5) consolidar_pendientes, ponerse_al_dia
backend/app/servicios/alertas.py                   (T5) emitir_alertas
backend/app/api/turnos.py                          (T6) GET /turnos se pone al día antes de responder
backend/app/api/coordinacion.py                    (T6, T8, T9) POST /consolidacion, POST /turnos/{id}/sin-cobertura, GET /indicadores/sin-cobertura
backend/app/repos/notificaciones.py                (T7) listar_de
backend/app/api/notificaciones.py                  (T7) GET /notificaciones, POST /notificaciones/{id}/leida
backend/app/servicios/sin_cobertura.py             (T8) marcar_sin_cobertura
backend/app/dominio/indicadores.py                 (T9) meses_del_rango
backend/app/repos/indicadores.py                   (T9) sin_cobertura_por_mes
backend/app/main.py                                (T2, T6, T7) routers nuevos
backend/tests/fabricas.py                          (T4) abrir_vacante
backend/CLAUDE.md, docs/prompts-principales.md     (T10)
```

---

### Task 1: Migración 0004 y marca de consolidación

**Files:**
- Create: `backend/migrations/versions/0004_consolidacion.py`
- Create: `backend/app/modelos/consolidacion.py`
- Modify: `backend/app/modelos/__init__.py`, `backend/app/modelos/turno.py` (`__table_args__`), `backend/scripts/seed.py:82`
- Test: `backend/tests/test_modelo_consolidacion.py`, `backend/tests/test_seed.py`

**Interfaces:**
- Produces: tabla `consolidacion_estado(id smallint PK = 1, consolidado_hasta date NULL)`; modelo `EstadoConsolidacion` exportado desde `app.modelos`; índice parcial `ix_turno_sin_consolidar`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`backend/tests/test_modelo_consolidacion.py`:

```python
from sqlalchemy import text

from app.modelos import EstadoConsolidacion
from fabricas import debe_fallar, guardar


def test_consolidacion_estado_tiene_rls(sesion):
    rls = sesion.execute(
        text("SELECT relrowsecurity FROM pg_class WHERE relname = 'consolidacion_estado'")
    ).scalar_one()
    assert rls is True


def test_consolidacion_estado_admite_una_sola_fila(sesion):
    guardar(sesion, EstadoConsolidacion(id=1, consolidado_hasta=None))
    debe_fallar(sesion, EstadoConsolidacion(id=2, consolidado_hasta=None), "ck_consolidacion_estado_unica")


def test_indice_de_turnos_sin_consolidar_es_parcial(sesion):
    definicion = sesion.execute(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_turno_sin_consolidar'")
    ).scalar_one()
    assert "WHERE (consolidado_en IS NULL)" in definicion
```

Agregar a `backend/tests/test_seed.py` (importar `EstadoConsolidacion` de `app.modelos` y `func`, `select` de `sqlalchemy` si faltan):

```python
def test_seed_vacia_la_marca_de_consolidacion(sesion):
    # Review Focus 1: con la marca vieja, después de reiniciar la demo no se consolidaría la historia.
    sesion.add(EstadoConsolidacion(id=1, consolidado_hasta=date(2026, 12, 1)))
    sesion.flush()
    cargar_datos_ejemplo(sesion)
    assert sesion.scalar(select(func.count()).select_from(EstadoConsolidacion)) == 0
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && .venv/bin/pytest tests/test_modelo_consolidacion.py tests/test_seed.py -v`
Expected: FAIL con `ImportError: cannot import name 'EstadoConsolidacion'`.

- [ ] **Step 3: Implementar**

`backend/migrations/versions/0004_consolidacion.py`:

```python
"""Marca de consolidación perezosa e índice de turnos sin consolidar (D20, D07)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-08
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_UPGRADE = [
    # D20: los turnos calculados con fecha anterior a consolidado_hasta ya se materializaron y consolidaron.
    # Una sola fila; NULL = todavía no se consolidó nada (se parte de la primera vigencia).
    """
    CREATE TABLE consolidacion_estado (
        id smallint PRIMARY KEY DEFAULT 1,
        consolidado_hasta date,
        CONSTRAINT ck_consolidacion_estado_unica CHECK (id = 1)
    )
    """,
    "ALTER TABLE consolidacion_estado ENABLE ROW LEVEL SECURITY",
    "CREATE INDEX ix_turno_sin_consolidar ON turno (fin) WHERE consolidado_en IS NULL",
]

_DOWNGRADE = [
    "DROP INDEX ix_turno_sin_consolidar",
    "DROP TABLE consolidacion_estado",
]


def upgrade() -> None:
    for sentencia in _UPGRADE:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _DOWNGRADE:
        op.execute(sentencia)
```

`backend/app/modelos/consolidacion.py`:

```python
from datetime import date

from sqlalchemy import CheckConstraint, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class EstadoConsolidacion(Base):
    """Marca de la consolidación perezosa (D20). Una sola fila, con id 1.

    Los turnos calculados con fecha anterior a consolidado_hasta ya se guardaron y consolidaron. La fila se
    bloquea en cada consolidación: dos consultas simultáneas se esperan (regla 8). El seed la vacía.
    """

    __tablename__ = "consolidacion_estado"
    __table_args__ = (CheckConstraint("id = 1", name="ck_consolidacion_estado_unica"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    consolidado_hasta: Mapped[date | None]
```

En `backend/app/modelos/turno.py`, agregar al final de `Turno.__table_args__` (después de `Index("ix_turno_asignado", "asignado_id")`):

```python
        Index("ix_turno_sin_consolidar", "fin", postgresql_where=text("consolidado_en IS NULL")),
```

En `backend/app/modelos/__init__.py`: `from app.modelos.consolidacion import EstadoConsolidacion` y agregar `"EstadoConsolidacion"` a `__all__` (orden alfabético).

En `backend/scripts/seed.py`, la línea del TRUNCATE queda:

```python
    sesion.execute(
        text("TRUNCATE usuario, horario_pactado, version_horario, consolidacion_estado RESTART IDENTITY CASCADE")
    )
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `cd backend && .venv/bin/pytest tests/test_modelo_consolidacion.py tests/test_seed.py tests/test_modelo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0004_consolidacion.py backend/app/modelos backend/scripts/seed.py backend/tests/test_modelo_consolidacion.py backend/tests/test_seed.py
git commit -m "Marca de consolidación perezosa e índice de turnos sin consolidar (D20)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Reloj de demo

**Files:**
- Modify: `backend/app/reloj.py`
- Create: `backend/app/api/demo.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_reloj.py`, `backend/tests/test_api_demo.py`

**Interfaces:**
- Produces: `RelojDesplazado(base: Reloj, desfase: timedelta)`; `desfase_demo() -> timedelta`; `fijar_desfase_demo(desfase: timedelta) -> None`; `get_reloj_sistema() -> Reloj` (hora real, dependencia sustituible en pruebas); `get_reloj()` devuelve `RelojDesplazado` si `modo_demo`. Endpoint `POST /api/demo/reloj` con cuerpo `{"ahora": "<ISO con zona>" | null}` y respuesta `{"ahora": "...", "desfaseHoras": float}`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Agregar a `backend/tests/test_reloj.py` (importar `RelojDesplazado`, `fijar_desfase_demo`, `get_reloj` de `app.reloj` y `Settings` de `app.config`):

```python
def test_reloj_desplazado_suma_el_desfase():
    base = RelojFijo(datetime(2026, 10, 12, 9, 0, tzinfo=ZONA))
    assert RelojDesplazado(base, timedelta(hours=50)).ahora() == datetime(2026, 10, 14, 11, 0, tzinfo=ZONA)


def test_get_reloj_aplica_el_desfase_solo_en_modo_demo(monkeypatch):
    fijar_desfase_demo(timedelta(days=3))
    try:
        monkeypatch.setattr("app.reloj.get_settings", lambda: Settings(modo_demo=True))
        reloj = get_reloj()
        assert isinstance(reloj, RelojDesplazado)
        assert reloj.ahora() - RelojSistema(ZONA).ahora() > timedelta(days=2, hours=23)
        monkeypatch.setattr("app.reloj.get_settings", lambda: Settings(modo_demo=False))
        assert isinstance(get_reloj(), RelojSistema)
    finally:
        fijar_desfase_demo(timedelta(0))
```

`backend/tests/test_api_demo.py`:

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings, get_settings
from app.main import app
from app.reloj import RelojFijo, desfase_demo, fijar_desfase_demo, get_reloj_sistema
from fabricas import crear_usuario, encabezados

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
REAL = datetime(2026, 10, 12, 9, 0, tzinfo=ZONA)


@pytest.fixture
def demo(cliente):
    app.dependency_overrides[get_settings] = lambda: Settings(modo_demo=True)
    app.dependency_overrides[get_reloj_sistema] = lambda: RelojFijo(REAL)
    yield
    app.dependency_overrides.pop(get_settings, None)
    app.dependency_overrides.pop(get_reloj_sistema, None)
    fijar_desfase_demo(timedelta(0))


def test_adelanta_el_reloj(demo, cliente, como_coordinador):
    r = cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00-03:00"})
    assert r.status_code == 200
    assert r.json() == {"ahora": "2026-10-15T08:00:00-03:00", "desfaseHoras": 71.0}
    assert desfase_demo() == timedelta(hours=71)


def test_no_vuelve_hacia_atras(demo, cliente, como_coordinador):
    # Review Focus 2: un turno ya consolidado quedaría en el futuro.
    cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00-03:00"})
    r = cliente.post("/api/demo/reloj", json={"ahora": "2026-10-13T08:00:00-03:00"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "RELOJ_HACIA_ATRAS"
    assert desfase_demo() == timedelta(hours=71)


def test_null_vuelve_a_la_hora_real(demo, cliente, como_coordinador):
    cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00-03:00"})
    r = cliente.post("/api/demo/reloj", json={"ahora": None})
    assert r.json() == {"ahora": "2026-10-12T09:00:00-03:00", "desfaseHoras": 0.0}
    assert desfase_demo() == timedelta(0)


def test_instante_sin_zona_es_error_de_validacion(demo, cliente, como_coordinador):
    r = cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDACION"


def test_un_medico_no_mueve_el_reloj(demo, cliente, sesion, reloj):
    cliente.headers.update(encabezados(crear_usuario(sesion, "Ana")))
    r = cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00-03:00"})
    assert r.status_code == 403
    assert desfase_demo() == timedelta(0)


def test_fuera_de_modo_demo_no_existe(cliente, como_coordinador):
    app.dependency_overrides[get_settings] = lambda: Settings(modo_demo=False)
    try:
        r = cliente.post("/api/demo/reloj", json={"ahora": "2026-10-15T08:00:00-03:00"})
    finally:
        app.dependency_overrides.pop(get_settings, None)
    assert r.status_code == 404
    assert r.json()["codigo"] == "NO_ENCONTRADO"
    assert desfase_demo() == timedelta(0)
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && .venv/bin/pytest tests/test_reloj.py tests/test_api_demo.py -v`
Expected: FAIL con `ImportError: cannot import name 'RelojDesplazado'`.

- [ ] **Step 3: Implementar**

En `backend/app/reloj.py`, después de `RelojFijo`, agregar y reemplazar `get_reloj`:

```python
class RelojDesplazado:
    """Reloj del modo demo (D27): la hora de otro reloj más un desfase que fija POST /demo/reloj."""

    def __init__(self, base: Reloj, desfase: timedelta) -> None:
        self._base = base
        self._desfase = desfase

    def ahora(self) -> datetime:
        return self._base.ahora() + self._desfase


# D27: desfase del reloj de demo. Vive en memoria: la demo corre en un solo proceso y reiniciarlo vuelve a la
# hora real. Fuera del modo demo no se usa.
_desfase_demo = timedelta(0)


def desfase_demo() -> timedelta:
    return _desfase_demo


def fijar_desfase_demo(desfase: timedelta) -> None:
    global _desfase_demo
    _desfase_demo = desfase


def get_reloj_sistema() -> Reloj:
    """Hora real, sin desfase. Solo la usa POST /demo/reloj para calcular el desfase."""
    return RelojSistema(get_settings().zona)


def get_reloj() -> Reloj:
    settings = get_settings()
    sistema = RelojSistema(settings.zona)
    if settings.modo_demo:
        return RelojDesplazado(sistema, _desfase_demo)
    return sistema
```

`backend/app/api/demo.py`:

```python
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
```

En `backend/app/main.py`: importar `demo` junto a los otros routers y agregar `api.include_router(demo.router)`.

- [ ] **Step 4: Correr y verificar que pasan**

Run: `cd backend && .venv/bin/pytest tests/test_reloj.py tests/test_api_demo.py tests/test_sin_hora_del_sistema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/reloj.py backend/app/api/demo.py backend/app/main.py backend/tests/test_reloj.py backend/tests/test_api_demo.py
git commit -m "Reloj de demo: POST /demo/reloj adelanta la hora solo en modo demo (D27)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Servicio de notificaciones

**Files:**
- Create: `backend/app/dominio/notificaciones.py`
- Create: `backend/app/servicios/notificaciones.py`
- Test: `backend/tests/test_notificaciones.py`

**Interfaces:**
- Consumes: `Umbral` de `app.dominio.alertas`, `exigir_zona`.
- Produces:
  - `TipoNotificacion(str, Enum)`: `VACANTE_URGENTE`, `ALERTA_SIN_COBERTURA`.
  - `mensaje_alerta(umbral: Umbral, inicio: datetime) -> str` (`inicio` ya en la zona del servicio).
  - `notificar(sesion: Session, usuario_ids: Iterable[int], tipo: TipoNotificacion, mensaje: str, ahora: datetime, turno: Turno | None = None, datos: dict[str, Any] | None = None) -> list[Notificacion]`: una por destinatario sin repetir; no hace commit. **Es la función que usa Mariano.**
  - `destinatarios(sesion: Session, rol: RolUsuario, dia: date, excepto: Collection[int] = ()) -> list[int]`: ids con acceso ese día, ordenados.

- [ ] **Step 1: Escribir las pruebas que fallan**

`backend/tests/test_notificaciones.py`:

```python
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.dominio.alertas import Umbral
from app.dominio.notificaciones import TipoNotificacion, mensaje_alerta
from app.modelos import EstadoUsuario, Notificacion, RolUsuario
from app.servicios.notificaciones import destinatarios, notificar
from fabricas import HOY, crear_horario_de_prueba, crear_usuario, guardar_turno

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
AHORA = datetime(2026, 10, 12, 9, 0, tzinfo=ZONA)


def test_mensaje_alerta_por_umbral():
    inicio = datetime(2026, 10, 17, 8, 0, tzinfo=ZONA)
    assert mensaje_alerta(Umbral.HORAS_48, inicio) == "La guardia del 17/10 a las 08:00 sigue sin cobertura: empieza en 48 h."
    assert mensaje_alerta(Umbral.HORAS_24, inicio) == "La guardia del 17/10 a las 08:00 sigue sin cobertura: empieza en 24 h."
    assert mensaje_alerta(Umbral.INICIO, inicio) == "La guardia del 17/10 a las 08:00 sigue sin cobertura: ya empezó."


def test_notificar_crea_una_por_destinatario_sin_repetir(sesion):
    ana = crear_usuario(sesion, "Ana")
    beto = crear_usuario(sesion, "Beto")
    creadas = notificar(sesion, [ana.id, beto.id, ana.id], TipoNotificacion.VACANTE_URGENTE, "Hola", AHORA)
    assert sorted(n.usuario_id for n in creadas) == sorted([ana.id, beto.id])
    filas = sesion.scalars(select(Notificacion)).all()
    assert len(filas) == 2
    assert all(n.tipo == "VACANTE_URGENTE" and n.creada_en == AHORA and n.leida_en is None for n in filas)


def test_notificar_guarda_turno_y_datos(sesion):
    ana = crear_usuario(sesion, "Ana")
    turno = guardar_turno(sesion, crear_horario_de_prueba(sesion, ana.id).id, date(2026, 10, 13))
    [n] = notificar(
        sesion, [ana.id], TipoNotificacion.ALERTA_SIN_COBERTURA, "x", AHORA, turno=turno, datos={"umbral": "48H"}
    )
    assert n.turno_id == turno.id
    assert n.datos == {"umbral": "48H"}


def test_notificar_sin_destinatarios_no_crea_nada(sesion):
    assert notificar(sesion, [], TipoNotificacion.VACANTE_URGENTE, "x", AHORA) == []


def test_notificar_rechaza_instante_sin_zona(sesion):
    ana = crear_usuario(sesion, "Ana")
    with pytest.raises(ValueError):
        notificar(sesion, [ana.id], TipoNotificacion.VACANTE_URGENTE, "x", datetime(2026, 10, 12, 9))


def test_destinatarios_son_los_que_tienen_acceso_ese_dia(sesion):
    activo = crear_usuario(sesion, "Activo")
    baja_hoy = crear_usuario(sesion, "Baja hoy", estado=EstadoUsuario.BAJA, fecha_baja=HOY)
    crear_usuario(sesion, "Baja vieja", estado=EstadoUsuario.BAJA)
    crear_usuario(sesion, "Pendiente", estado=EstadoUsuario.PENDIENTE)
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    assert destinatarios(sesion, RolUsuario.MEDICO, HOY) == sorted([activo.id, baja_hoy.id])
    assert destinatarios(sesion, RolUsuario.COORDINADOR, HOY) == [enzo.id]
    assert destinatarios(sesion, RolUsuario.MEDICO, HOY, excepto={activo.id}) == [baja_hoy.id]
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && .venv/bin/pytest tests/test_notificaciones.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.dominio.notificaciones'`.

- [ ] **Step 3: Implementar**

`backend/app/dominio/notificaciones.py`:

```python
"""Tipos y textos de las notificaciones dentro de la app (D05). Lógica pura: sin base de datos ni FastAPI."""

from datetime import datetime
from enum import Enum

from app.dominio.alertas import Umbral
from app.dominio.tiempo import exigir_zona


class TipoNotificacion(str, Enum):
    """Lista cerrada de tipos (la columna es texto: agregar uno no necesita migración)."""

    VACANTE_URGENTE = "VACANTE_URGENTE"  # D05, D15: la crea generar_vacante (F3, Mariano)
    ALERTA_SIN_COBERTURA = "ALERTA_SIN_COBERTURA"  # D19


_CUANDO = {
    Umbral.HORAS_48: "empieza en 48 h",
    Umbral.HORAS_24: "empieza en 24 h",
    Umbral.INICIO: "ya empezó",
}


def mensaje_alerta(umbral: Umbral, inicio: datetime) -> str:
    """Texto de la alerta a coordinadores. `inicio` tiene que venir en la zona del servicio."""
    exigir_zona(inicio)
    return f"La guardia del {inicio:%d/%m} a las {inicio:%H:%M} sigue sin cobertura: {_CUANDO[umbral]}."
```

`backend/app/servicios/notificaciones.py`:

```python
"""Notificaciones dentro de la app (D05). No hace commit: la notificación va en la transacción de la acción (D22)."""

from collections.abc import Collection, Iterable
from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.dominio.notificaciones import TipoNotificacion
from app.dominio.tiempo import exigir_zona
from app.modelos import EstadoUsuario, Notificacion, RolUsuario, Turno, Usuario


def notificar(
    sesion: Session,
    usuario_ids: Iterable[int],
    tipo: TipoNotificacion,
    mensaje: str,
    ahora: datetime,
    turno: Turno | None = None,
    datos: dict[str, Any] | None = None,
) -> list[Notificacion]:
    """Una notificación por destinatario (sin repetir), con creada_en = ahora del reloj inyectable (D27)."""
    exigir_zona(ahora)
    filas = [
        Notificacion(
            usuario_id=usuario_id,
            tipo=tipo.value,
            mensaje=mensaje,
            turno_id=turno.id if turno is not None else None,
            datos=dict(datos or {}),
            creada_en=ahora,
        )
        for usuario_id in dict.fromkeys(usuario_ids)
    ]
    sesion.add_all(filas)
    sesion.flush()
    return filas


def destinatarios(sesion: Session, rol: RolUsuario, dia: date, excepto: Collection[int] = ()) -> list[int]:
    """Ids de quienes tienen acceso ese día: ACTIVO, o BAJA hasta su fecha de baja inclusive (D24)."""
    consulta = (
        select(Usuario.id)
        .where(
            Usuario.rol == rol,
            or_(
                Usuario.estado == EstadoUsuario.ACTIVO,
                and_(Usuario.estado == EstadoUsuario.BAJA, Usuario.fecha_baja >= dia),
            ),
        )
        .order_by(Usuario.id)
    )
    return [usuario_id for usuario_id in sesion.scalars(consulta) if usuario_id not in excepto]
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `cd backend && .venv/bin/pytest tests/test_notificaciones.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/dominio/notificaciones.py backend/app/servicios/notificaciones.py backend/tests/test_notificaciones.py
git commit -m "Servicio para crear notificaciones y elegir destinatarios con acceso (D05, D22, D24)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Consolidación perezosa e idempotente

**Files:**
- Create: `backend/app/repos/consolidacion.py`
- Create: `backend/app/servicios/consolidacion.py`
- Modify: `backend/tests/fabricas.py` (agregar `abrir_vacante`)
- Test: `backend/tests/test_servicio_consolidacion.py`

**Interfaces:**
- Consumes: `consolidar`, `TurnoConsolidable` (`app.dominio.consolidacion`); `calcular_turnos`, `formatear_id_turno` (`app.dominio.calendario`); `versiones_en_rango` (`app.repos.horarios`); `hoy`, `Reloj`; `EstadoConsolidacion` (T1).
- Produces:
  - `@dataclass(frozen=True) ResultadoConsolidacion(consolidados: int, vacantes_sin_cobertura: int)`.
  - `consolidar_pendientes(sesion: Session, reloj: Reloj, zona: ZoneInfo) -> ResultadoConsolidacion`: bloquea la marca; guarda y consolida los turnos calculados terminados desde la marca (`INSERT ... ON CONFLICT DO NOTHING`); consolida los turnos guardados terminados; cierra como `SIN_COBERTURA` las vacantes abiertas de esos turnos (decisión 3); avanza la marca. No hace commit.
  - En `fabricas.py`: `abrir_vacante(sesion: Session, turno: Turno, generada_por_id: int, creada_en: datetime) -> Vacante`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Agregar a `backend/tests/fabricas.py` (importar `EstadoVacante`, `Vacante` de `app.modelos`):

```python
def abrir_vacante(sesion: Session, turno: Turno, generada_por_id: int, creada_en: datetime) -> Vacante:
    """Vacante ABIERTA cargada directo en la base (las reglas de generar vacante son de F3)."""
    vacante = Vacante(turno_id=turno.id, generada_por_id=generada_por_id, estado=EstadoVacante.ABIERTA, creada_en=creada_en)
    guardar(sesion, vacante)
    return vacante
```

`backend/tests/test_servicio_consolidacion.py`:

```python
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.modelos import EstadoConsolidacion, EstadoVacante, EventoTurno, TipoEventoTurno, Turno
from app.reloj import RelojFijo
from app.servicios.consolidacion import ResultadoConsolidacion, consolidar_pendientes
from fabricas import abrir_vacante, bloqueado_hasta_commit, crear_horario_de_prueba, crear_usuario, guardar_turno

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
MARTES_PASADOS = [date(2026, 9, 8), date(2026, 9, 15), date(2026, 9, 22), date(2026, 9, 29), date(2026, 10, 6)]


def turnos(sesion, horario_id):
    return sesion.scalars(select(Turno).where(Turno.horario_id == horario_id).order_by(Turno.fecha)).all()


def marca(sesion):
    return sesion.scalar(select(EstadoConsolidacion.consolidado_hasta))


def test_guarda_y_consolida_los_turnos_calculados_terminados(sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    horario = crear_horario_de_prueba(sesion, ana.id)

    resultado = consolidar_pendientes(sesion, reloj, ZONA)

    assert resultado == ResultadoConsolidacion(consolidados=5, vacantes_sin_cobertura=0)
    filas = turnos(sesion, horario.id)
    assert [t.fecha for t in filas] == MARTES_PASADOS
    assert all(t.realizador_id == ana.id and t.consolidado_en == reloj.ahora() for t in filas)
    assert filas[0].inicio == datetime(2026, 9, 8, 8, 0, tzinfo=ZONA)
    assert filas[0].fin == datetime(2026, 9, 8, 20, 0, tzinfo=ZONA)
    assert filas[0].titular_id == ana.id
    assert marca(sesion) == date(2026, 10, 12)


def test_es_idempotente(sesion, reloj):
    crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id)
    consolidar_pendientes(sesion, reloj, ZONA)
    assert consolidar_pendientes(sesion, reloj, ZONA) == ResultadoConsolidacion(0, 0)
    assert sesion.scalar(select(func.count()).select_from(Turno)) == 5


def test_turno_en_curso_no_se_consolida_y_la_marca_lo_espera(sesion, reloj):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id)
    reloj.avanzar(timedelta(days=1, hours=1))  # martes 13/10 10:00: el turno de hoy está en curso

    consolidar_pendientes(sesion, reloj, ZONA)
    assert [t.fecha for t in turnos(sesion, horario.id)] == MARTES_PASADOS
    assert marca(sesion) == date(2026, 10, 13)

    reloj.avanzar(timedelta(hours=10))  # 20:00: terminó justo
    assert consolidar_pendientes(sesion, reloj, ZONA).consolidados == 1


def test_turno_que_cruza_medianoche_se_consolida_al_terminar(sesion, reloj):
    carlos = crear_usuario(sesion, "Carlos")
    # domingo 20:00 a lunes 08:00, desde el domingo 11/10
    horario = crear_horario_de_prueba(sesion, carlos.id, dia=7, hora=time(20), dur=12, desde=date(2026, 10, 11))
    consolidar_pendientes(sesion, reloj, ZONA)
    [turno] = turnos(sesion, horario.id)
    assert turno.fecha == date(2026, 10, 11)
    assert turno.realizador_id == carlos.id


def test_horario_sin_titular_se_consolida_sin_realizador(sesion, reloj):
    horario = crear_horario_de_prueba(sesion, None)
    consolidar_pendientes(sesion, reloj, ZONA)
    assert all(t.realizador_id is None for t in turnos(sesion, horario.id))


def test_turno_guardado_con_asignado_lo_hace_el_asignado(sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    beto = crear_usuario(sesion, "Beto")
    horario = crear_horario_de_prueba(sesion, ana.id)
    guardado = guardar_turno(sesion, horario.id, date(2026, 10, 6), asignado_id=beto.id)

    resultado = consolidar_pendientes(sesion, reloj, ZONA)

    assert resultado.consolidados == 5  # 4 calculados + el guardado; el calculado del 6/10 no se duplica
    assert guardado.realizador_id == beto.id
    assert guardado.consolidado_en == reloj.ahora()


def test_turno_guardado_usa_su_foto_y_no_la_plantilla(sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    beto = crear_usuario(sesion, "Beto")
    horario = crear_horario_de_prueba(sesion, ana.id)
    guardado = guardar_turno(sesion, horario.id, date(2026, 10, 6))
    guardado.titular_id = beto.id  # la foto (D11) difiere de la plantilla actual
    sesion.flush()
    consolidar_pendientes(sesion, reloj, ZONA)
    assert guardado.realizador_id == beto.id


def test_vacante_abierta_al_terminar_queda_sin_cobertura(sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    horario = crear_horario_de_prueba(sesion, ana.id)
    guardado = guardar_turno(sesion, horario.id, date(2026, 10, 6))
    vacante = abrir_vacante(sesion, guardado, ana.id, datetime(2026, 10, 1, 10, 0, tzinfo=ZONA))

    resultado = consolidar_pendientes(sesion, reloj, ZONA)

    assert resultado.vacantes_sin_cobertura == 1
    assert guardado.realizador_id is None
    assert guardado.sin_cobertura_en == reloj.ahora()
    assert vacante.estado == EstadoVacante.SIN_COBERTURA
    assert vacante.cerrada_en == reloj.ahora()
    [evento] = sesion.scalars(select(EventoTurno).where(EventoTurno.turno_id == guardado.id)).all()
    assert evento.tipo == TipoEventoTurno.TURNO_SIN_COBERTURA
    assert evento.actor_id is None
    assert evento.datos == {"vacante_id": vacante.id, "al_consolidar": True}


def test_horario_cerrado_solo_consolida_su_vigencia(sesion, reloj):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id, hasta=date(2026, 9, 20))
    consolidar_pendientes(sesion, reloj, ZONA)
    assert [t.fecha for t in turnos(sesion, horario.id)] == [date(2026, 9, 8), date(2026, 9, 15)]


def test_sin_horarios_no_hace_nada(sesion, reloj):
    assert consolidar_pendientes(sesion, reloj, ZONA) == ResultadoConsolidacion(0, 0)


@pytest.mark.commit_real
def test_dos_consolidaciones_simultaneas_dejan_una_fila_por_turno(fabrica_sesiones):
    # Review Focus 4.
    reloj = RelojFijo(datetime(2026, 10, 12, 9, 0, tzinfo=ZONA))
    with fabrica_sesiones() as s:
        crear_horario_de_prueba(s, crear_usuario(s, "Ana").id)
        s.commit()

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        primera = consolidar_pendientes(s1, reloj, ZONA)
        resultado = bloqueado_hasta_commit(s1, lambda: consolidar_pendientes(s2, reloj, ZONA))
        s2.commit()

    assert primera.consolidados == 5
    assert resultado == {"valor": ResultadoConsolidacion(0, 0)}
    with fabrica_sesiones() as s:
        assert s.scalar(select(func.count()).select_from(Turno)) == 5
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && .venv/bin/pytest tests/test_servicio_consolidacion.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.servicios.consolidacion'`.

- [ ] **Step 3: Implementar**

`backend/app/repos/consolidacion.py`:

```python
"""Consultas de la consolidación perezosa (D20). No hacen commit."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modelos import EstadoConsolidacion, EstadoVacante, Turno, Vacante, VersionHorario


def bloquear_marca(sesion: Session) -> date | None:
    """Devuelve la marca y bloquea su fila hasta el fin de la transacción (regla 8). Crea la fila si falta."""
    sesion.execute(insert(EstadoConsolidacion).values(id=1).on_conflict_do_nothing(index_elements=["id"]))
    return sesion.execute(
        select(EstadoConsolidacion.consolidado_hasta).where(EstadoConsolidacion.id == 1).with_for_update()
    ).scalar_one()


def guardar_marca(sesion: Session, fecha: date) -> None:
    sesion.execute(update(EstadoConsolidacion).where(EstadoConsolidacion.id == 1).values(consolidado_hasta=fecha))


def primera_vigencia(sesion: Session) -> date | None:
    return sesion.scalar(select(func.min(VersionHorario.vigente_desde)))


def insertar_consolidados(sesion: Session, filas: list[dict[str, Any]]) -> int:
    """Guarda turnos ya consolidados; si el turno ya tenía fila (D11), no la toca. Devuelve cuántos insertó."""
    if not filas:
        return 0
    insertados = sesion.execute(
        insert(Turno).values(filas).on_conflict_do_nothing(constraint="ux_turno_horario_fecha").returning(Turno.id)
    )
    return len(insertados.all())


def turnos_guardados_por_consolidar(sesion: Session, ahora: datetime) -> list[tuple[Turno, Vacante | None]]:
    """Turnos guardados que terminaron y no se consolidaron, bloqueados por id, con su vacante abierta (bloqueada)."""
    turnos = list(
        sesion.scalars(
            select(Turno)
            .where(Turno.consolidado_en.is_(None), Turno.fin <= ahora)
            .order_by(Turno.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    if not turnos:
        return []
    abiertas = {
        vacante.turno_id: vacante
        for vacante in sesion.scalars(
            select(Vacante)
            .where(Vacante.turno_id.in_([t.id for t in turnos]), Vacante.estado == EstadoVacante.ABIERTA)
            .order_by(Vacante.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    return [(turno, abiertas.get(turno.id)) for turno in turnos]
```

`backend/app/servicios/consolidacion.py`:

```python
"""Consolidación perezosa e idempotente (D20): corre antes de responder, sin proceso programado. No hace commit."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.dominio.calendario import TurnoCalculado, calcular_turnos, formatear_id_turno
from app.dominio.consolidacion import Consolidacion, TurnoConsolidable, consolidar
from app.modelos import EstadoVacante, EventoTurno, TipoEventoTurno
from app.reloj import Reloj, hoy
from app.repos.consolidacion import (
    bloquear_marca,
    guardar_marca,
    insertar_consolidados,
    primera_vigencia,
    turnos_guardados_por_consolidar,
)
from app.repos.horarios import versiones_en_rango


@dataclass(frozen=True)
class ResultadoConsolidacion:
    consolidados: int
    vacantes_sin_cobertura: int


def consolidar_pendientes(sesion: Session, reloj: Reloj, zona: ZoneInfo) -> ResultadoConsolidacion:
    ahora = reloj.ahora()
    marca = bloquear_marca(sesion)
    calculados = _consolidar_calculados(sesion, marca, hoy(reloj), ahora, zona)
    guardados, cerradas = _consolidar_guardados(sesion, ahora)
    return ResultadoConsolidacion(calculados + guardados, cerradas)


def _consolidar_calculados(sesion: Session, marca: date | None, dia: date, ahora: datetime, zona: ZoneInfo) -> int:
    """Turnos que nunca se guardaron: se calculan desde la plantilla y se guardan ya consolidados (D11)."""
    desde = marca if marca is not None else primera_vigencia(sesion)
    if desde is None or desde > dia:
        return 0
    turnos = [t for t in calcular_turnos(versiones_en_rango(sesion, desde, dia), desde, dia, zona) if t.fecha >= desde]
    por_id = {t.id: t for t in turnos}
    pendientes = [
        TurnoConsolidable(t.id, t.fin, t.titular.id if t.titular else None, None, False, False, None) for t in turnos
    ]
    filas = [_fila(por_id[c.turno_id], c) for c in consolidar(pendientes, ahora)]
    insertados = insertar_consolidados(sesion, filas)
    # La próxima vez se parte del primer turno que todavía no terminó (o de hoy): nunca se retrocede.
    sin_terminar = [t.fecha for t in turnos if t.fin > ahora]
    guardar_marca(sesion, max(desde, min(sin_terminar, default=dia)))
    return insertados


def _fila(turno: TurnoCalculado, consolidacion: Consolidacion) -> dict[str, Any]:
    """Fila del turno con la foto de su versión (D11), ya consolidada."""
    return {
        "horario_id": turno.horario_id,
        "fecha": turno.fecha,
        "version_id": turno.version_id,
        "inicio": turno.inicio,
        "fin": turno.fin,
        "titular_id": turno.titular.id if turno.titular else None,
        "realizador_id": consolidacion.realizador_id,
        "consolidado_en": consolidacion.consolidado_en,
    }


def _consolidar_guardados(sesion: Session, ahora: datetime) -> tuple[int, int]:
    """Turnos con fila: se usa su foto (D11, D12). Una vacante abierta al terminar queda SIN_COBERTURA (D19, D31)."""
    pendientes = turnos_guardados_por_consolidar(sesion, ahora)
    por_id = {formatear_id_turno(t.horario_id, t.fecha): (t, v) for t, v in pendientes}
    consolidables = [
        TurnoConsolidable(
            turno_id,
            turno.fin,
            turno.titular_id,
            turno.asignado_id,
            vacante is not None,
            turno.sin_cobertura_en is not None,
            turno.consolidado_en,
        )
        for turno_id, (turno, vacante) in por_id.items()
    ]
    cerradas = 0
    for consolidacion in consolidar(consolidables, ahora):
        turno, vacante = por_id[consolidacion.turno_id]
        if vacante is not None:
            vacante.estado = EstadoVacante.SIN_COBERTURA
            vacante.cerrada_en = ahora
            if turno.sin_cobertura_en is None:
                turno.sin_cobertura_en = ahora
            sesion.add(
                EventoTurno(
                    turno_id=turno.id,
                    tipo=TipoEventoTurno.TURNO_SIN_COBERTURA,
                    actor_id=None,
                    ocurrido_en=ahora,
                    datos={"vacante_id": vacante.id, "al_consolidar": True},
                )
            )
            cerradas += 1
        turno.realizador_id = consolidacion.realizador_id
        turno.consolidado_en = consolidacion.consolidado_en
    sesion.flush()
    return len(por_id), cerradas
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `cd backend && .venv/bin/pytest tests/test_servicio_consolidacion.py tests/test_consolidacion.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repos/consolidacion.py backend/app/servicios/consolidacion.py backend/tests/fabricas.py backend/tests/test_servicio_consolidacion.py
git commit -m "Consolidación perezosa e idempotente de turnos calculados y guardados (D11, D19, D20, D31)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Alertas escalonadas y puesta al día

**Files:**
- Create: `backend/app/servicios/alertas.py`
- Modify: `backend/app/servicios/consolidacion.py` (agregar `ponerse_al_dia`)
- Test: `backend/tests/test_servicio_alertas.py`

**Interfaces:**
- Consumes: `alertas_pendientes`, `Umbral` (`app.dominio.alertas`); `notificar`, `destinatarios` (T3); `mensaje_alerta`, `TipoNotificacion` (T3); `consolidar_pendientes` (T4).
- Produces:
  - `emitir_alertas(sesion: Session, reloj: Reloj, zona: ZoneInfo) -> int`: cantidad de turnos para los que se notificó. Registra un `ALERTA_SIN_COBERTURA` por umbral vencido con `INSERT ... ON CONFLICT DO NOTHING` y notifica a los coordinadores con acceso **solo el umbral más reciente** de los que registró (decisión 6). No hace commit.
  - `@dataclass(frozen=True) ResultadoPuestaAlDia(consolidados: int, vacantes_sin_cobertura: int, alertas: int)` y `ponerse_al_dia(sesion, reloj, zona) -> ResultadoPuestaAlDia` (consolida y después emite alertas).

- [ ] **Step 1: Escribir las pruebas que fallan**

`backend/tests/test_servicio_alertas.py`:

```python
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.modelos import EventoTurno, Notificacion, RolUsuario, TipoEventoTurno
from app.reloj import RelojFijo
from app.servicios.alertas import emitir_alertas
from app.servicios.consolidacion import ResultadoPuestaAlDia, ponerse_al_dia
from fabricas import abrir_vacante, bloqueado_hasta_commit, crear_horario_de_prueba, crear_usuario, guardar_turno

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
INICIO = datetime(2026, 10, 13, 8, 0, tzinfo=ZONA)  # turno del martes 13/10, 08:00 a 20:00


def preparar(sesion, vacante_desde=datetime(2026, 10, 9, 10, 0, tzinfo=ZONA)):
    ana = crear_usuario(sesion, "Ana")
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    turno = guardar_turno(sesion, crear_horario_de_prueba(sesion, ana.id).id, date(2026, 10, 13))
    abrir_vacante(sesion, turno, ana.id, vacante_desde)
    return ana, enzo, turno


def alertas(sesion, turno):
    return sorted(
        e.datos["umbral"]
        for e in sesion.scalars(
            select(EventoTurno).where(
                EventoTurno.turno_id == turno.id, EventoTurno.tipo == TipoEventoTurno.ALERTA_SIN_COBERTURA
            )
        )
    )


def test_a_las_48_h_avisa_a_los_coordinadores_y_no_a_los_medicos(sesion):
    ana, enzo, turno = preparar(sesion)
    otro = crear_usuario(sesion, "Otro coordinador", rol=RolUsuario.COORDINADOR)
    reloj = RelojFijo(INICIO - timedelta(hours=48))

    assert emitir_alertas(sesion, reloj, ZONA) == 1

    assert alertas(sesion, turno) == ["48H"]
    notificaciones = sesion.scalars(select(Notificacion).order_by(Notificacion.usuario_id)).all()
    assert [n.usuario_id for n in notificaciones] == [enzo.id, otro.id]
    assert all(n.tipo == "ALERTA_SIN_COBERTURA" and n.turno_id == turno.id for n in notificaciones)
    assert notificaciones[0].datos == {"umbral": "48H"}
    assert notificaciones[0].mensaje == "La guardia del 13/10 a las 08:00 sigue sin cobertura: empieza en 48 h."
    evento = sesion.scalars(select(EventoTurno)).one()
    assert evento.actor_id is None
    assert evento.ocurrido_en == reloj.ahora()


def test_no_repite_un_umbral(sesion):
    _, _, turno = preparar(sesion)
    reloj = RelojFijo(INICIO - timedelta(hours=47))
    emitir_alertas(sesion, reloj, ZONA)
    assert emitir_alertas(sesion, reloj, ZONA) == 0
    assert len(sesion.scalars(select(Notificacion)).all()) == 1


def test_si_vencieron_varios_umbrales_avisa_solo_el_mas_reciente(sesion):
    # Review Focus 3: reloj de demo adelantado o servidor caído.
    _, enzo, turno = preparar(sesion)
    reloj = RelojFijo(INICIO + timedelta(minutes=5))

    emitir_alertas(sesion, reloj, ZONA)

    assert alertas(sesion, turno) == ["24H", "48H", "INICIO"]
    [notificacion] = sesion.scalars(select(Notificacion)).all()
    assert notificacion.usuario_id == enzo.id
    assert notificacion.datos == {"umbral": "INICIO"}


def test_vacante_abierta_despues_de_un_umbral_no_lo_dispara(sesion):
    _, _, turno = preparar(sesion, vacante_desde=INICIO - timedelta(hours=30))
    assert emitir_alertas(sesion, RelojFijo(INICIO - timedelta(hours=29)), ZONA) == 0
    emitir_alertas(sesion, RelojFijo(INICIO - timedelta(hours=24)), ZONA)
    assert alertas(sesion, turno) == ["24H"]


def test_turno_sin_vacante_o_terminado_no_alerta(sesion):
    ana = crear_usuario(sesion, "Ana")
    crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    horario = crear_horario_de_prueba(sesion, ana.id)
    guardar_turno(sesion, horario.id, date(2026, 10, 13))  # sin vacante
    terminado = guardar_turno(sesion, horario.id, date(2026, 10, 6))
    abrir_vacante(sesion, terminado, ana.id, datetime(2026, 10, 1, tzinfo=ZONA))
    assert emitir_alertas(sesion, RelojFijo(INICIO), ZONA) == 0


def test_sin_coordinadores_registra_el_evento_igual(sesion):
    ana = crear_usuario(sesion, "Ana")
    turno = guardar_turno(sesion, crear_horario_de_prueba(sesion, ana.id).id, date(2026, 10, 13))
    abrir_vacante(sesion, turno, ana.id, datetime(2026, 10, 9, tzinfo=ZONA))
    emitir_alertas(sesion, RelojFijo(INICIO - timedelta(hours=48)), ZONA)
    assert alertas(sesion, turno) == ["48H"]
    assert sesion.scalars(select(Notificacion)).all() == []


def test_ponerse_al_dia_consolida_y_alerta(sesion, reloj):
    preparar(sesion)  # reloj: lunes 12/10 09:00, 23 h antes del inicio
    resultado = ponerse_al_dia(sesion, reloj, ZONA)
    assert resultado == ResultadoPuestaAlDia(consolidados=5, vacantes_sin_cobertura=0, alertas=1)


@pytest.mark.commit_real
def test_dos_pasadas_simultaneas_dejan_una_sola_alerta(fabrica_sesiones):
    # Review Focus 4: dos coordinadores consultando a la vez.
    reloj = RelojFijo(INICIO - timedelta(hours=48))
    with fabrica_sesiones() as s:
        preparar(s)
        s.commit()

    with fabrica_sesiones() as s1, fabrica_sesiones() as s2:
        assert emitir_alertas(s1, reloj, ZONA) == 1
        resultado = bloqueado_hasta_commit(s1, lambda: emitir_alertas(s2, reloj, ZONA))
        s2.commit()

    assert resultado == {"valor": 0}
    with fabrica_sesiones() as s:
        assert len(s.scalars(select(Notificacion)).all()) == 1
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && .venv/bin/pytest tests/test_servicio_alertas.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.servicios.alertas'`.

- [ ] **Step 3: Implementar**

`backend/app/servicios/alertas.py`:

```python
"""Alertas escalonadas a coordinadores por vacantes sin cubrir (D19). No hace commit."""

from collections import defaultdict
from collections.abc import Collection
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select, text
from sqlalchemy.orm import Session

from app.dominio.alertas import Umbral, alertas_pendientes
from app.dominio.notificaciones import TipoNotificacion, mensaje_alerta
from app.modelos import EstadoVacante, EventoTurno, RolUsuario, TipoEventoTurno, Turno, Vacante
from app.reloj import Reloj, hoy
from app.servicios.notificaciones import destinatarios, notificar

ANTICIPACION_MAXIMA = timedelta(hours=48)

# D19, regla 8: el índice único ux_evento_alerta_por_umbral garantiza una alerta por turno y umbral aunque dos
# pedidos lleguen juntos; el segundo espera al primero y no inserta nada.
_REGISTRAR_ALERTA = text(
    """
    INSERT INTO evento_turno (turno_id, tipo, actor_id, ocurrido_en, datos)
    VALUES (:turno_id, 'ALERTA_SIN_COBERTURA', NULL, :ahora, jsonb_build_object('umbral', CAST(:umbral AS text)))
    ON CONFLICT (turno_id, (datos->>'umbral')) WHERE tipo = 'ALERTA_SIN_COBERTURA' DO NOTHING
    RETURNING id
    """
)


def emitir_alertas(sesion: Session, reloj: Reloj, zona: ZoneInfo) -> int:
    ahora = reloj.ahora()
    filas = sesion.execute(
        select(Turno, Vacante)
        .join(Vacante, and_(Vacante.turno_id == Turno.id, Vacante.estado == EstadoVacante.ABIERTA))
        .where(Turno.inicio <= ahora + ANTICIPACION_MAXIMA, Turno.fin > ahora, Turno.consolidado_en.is_(None))
        .order_by(Turno.inicio, Turno.id)
    ).all()
    if not filas:
        return 0
    enviadas = _enviadas(sesion, [turno.id for turno, _ in filas])
    coordinadores: list[int] | None = None
    notificados = 0
    for turno, vacante in filas:
        vencidos = alertas_pendientes(turno.inicio, turno.fin, vacante.creada_en, ahora, enviadas[turno.id])
        registrados = [umbral for umbral in vencidos if _registrar(sesion, turno.id, umbral, ahora)]
        if not registrados:
            continue
        if coordinadores is None:
            coordinadores = destinatarios(sesion, RolUsuario.COORDINADOR, hoy(reloj))
        # Decisión 6 del plan: si vencieron varios a la vez, se avisa solo el más reciente.
        umbral = registrados[-1]
        notificar(
            sesion,
            coordinadores,
            TipoNotificacion.ALERTA_SIN_COBERTURA,
            mensaje_alerta(umbral, turno.inicio.astimezone(zona)),
            ahora,
            turno=turno,
            datos={"umbral": umbral.value},
        )
        notificados += 1
    return notificados


def _enviadas(sesion: Session, turno_ids: Collection[int]) -> defaultdict[int, set[Umbral]]:
    resultado: defaultdict[int, set[Umbral]] = defaultdict(set)
    filas = sesion.execute(
        select(EventoTurno.turno_id, EventoTurno.datos["umbral"].astext).where(
            EventoTurno.turno_id.in_(turno_ids), EventoTurno.tipo == TipoEventoTurno.ALERTA_SIN_COBERTURA
        )
    )
    for turno_id, umbral in filas:
        resultado[turno_id].add(Umbral(umbral))
    return resultado


def _registrar(sesion: Session, turno_id: int, umbral: Umbral, ahora: datetime) -> bool:
    insertado = sesion.execute(_REGISTRAR_ALERTA, {"turno_id": turno_id, "ahora": ahora, "umbral": umbral.value})
    return insertado.first() is not None
```

Agregar al final de `backend/app/servicios/consolidacion.py` (agregar arriba `from app.servicios.alertas import emitir_alertas`; no hay import circular: `alertas` no importa `consolidacion`):

```python
@dataclass(frozen=True)
class ResultadoPuestaAlDia:
    consolidados: int
    vacantes_sin_cobertura: int
    alertas: int


def ponerse_al_dia(sesion: Session, reloj: Reloj, zona: ZoneInfo) -> ResultadoPuestaAlDia:
    """Lo que antes haría un proceso programado (D19, D20): consolidar y después avisar. No hace commit."""
    consolidacion = consolidar_pendientes(sesion, reloj, zona)
    alertas = emitir_alertas(sesion, reloj, zona)
    return ResultadoPuestaAlDia(consolidacion.consolidados, consolidacion.vacantes_sin_cobertura, alertas)
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `cd backend && .venv/bin/pytest tests/test_servicio_alertas.py tests/test_alertas.py tests/test_servicio_consolidacion.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/servicios/alertas.py backend/app/servicios/consolidacion.py backend/tests/test_servicio_alertas.py
git commit -m "Alertas escalonadas a coordinadores, una por turno y umbral (D19, D22)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Consolidar antes del calendario y forzar la consolidación

**Files:**
- Modify: `backend/app/api/turnos.py` (`listar_turnos`)
- Create: `backend/app/api/coordinacion.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_consolidacion.py`

**Interfaces:**
- Consumes: `ponerse_al_dia`, `ResultadoPuestaAlDia` (T5).
- Produces: `GET /api/turnos` consolida y alerta (y hace commit) antes de calcular la respuesta, con el JSON de siempre. `POST /api/consolidacion` (solo coordinadores) responde `{"consolidados": int, "vacantesSinCobertura": int, "alertas": int}`. Router `app/api/coordinacion.py` con `router = APIRouter()` (T8 y T9 le agregan rutas).

- [ ] **Step 1: Escribir las pruebas que fallan**

`backend/tests/test_api_consolidacion.py`:

```python
from sqlalchemy import func, select

from app.modelos import Turno
from fabricas import crear_horario_de_prueba, crear_usuario, encabezados


def consolidados(sesion):
    return sesion.scalar(select(func.count()).select_from(Turno).where(Turno.consolidado_en.is_not(None)))


def test_get_turnos_consolida_antes_de_responder(cliente, sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    cliente.headers.update(encabezados(ana))
    horario = crear_horario_de_prueba(sesion, ana.id)

    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-18"})

    assert r.status_code == 200
    assert [t["id"] for t in r.json()] == [f"{horario.id}:2026-10-13"]
    assert consolidados(sesion) == 5


def test_post_consolidacion_devuelve_lo_que_hizo_y_es_idempotente(cliente, sesion, como_coordinador):
    crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id)

    r = cliente.post("/api/consolidacion")
    assert r.status_code == 200
    assert r.json() == {"consolidados": 5, "vacantesSinCobertura": 0, "alertas": 0}

    assert cliente.post("/api/consolidacion").json() == {"consolidados": 0, "vacantesSinCobertura": 0, "alertas": 0}


def test_un_medico_no_fuerza_la_consolidacion(cliente, sesion, reloj):
    cliente.headers.update(encabezados(crear_usuario(sesion, "Ana")))
    r = cliente.post("/api/consolidacion")
    assert r.status_code == 403
    assert r.json()["codigo"] == "SIN_PERMISO"
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && .venv/bin/pytest tests/test_api_consolidacion.py -v`
Expected: FAIL (`consolidados(sesion) == 0` en la primera; 404 en `/api/consolidacion`).

- [ ] **Step 3: Implementar**

En `backend/app/api/turnos.py`: importar `from app.reloj import Reloj, get_reloj` y `from app.servicios.consolidacion import ponerse_al_dia`; agregar el parámetro `reloj: Reloj = Depends(get_reloj)` a `listar_turnos` y, después de las validaciones del rango y antes de `versiones_en_rango`:

```python
    zona = get_settings().zona
    # D20: la consolidación es perezosa; se hace antes de responder el calendario y se confirma aparte.
    ponerse_al_dia(db, reloj, zona)
    db.commit()
    versiones = versiones_en_rango(db, desde, hasta)
    turnos = calcular_turnos(versiones, desde, hasta, zona)
```

`backend/app/api/coordinacion.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import requiere_coordinador
from app.config import get_settings
from app.db import get_db
from app.modelos import Usuario
from app.reloj import Reloj, get_reloj
from app.servicios.consolidacion import ponerse_al_dia

router = APIRouter()


class PuestaAlDiaOut(Esquema):
    consolidados: int
    vacantes_sin_cobertura: int
    alertas: int


@router.post("/consolidacion", response_model=PuestaAlDiaOut)
def forzar_consolidacion(
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> PuestaAlDiaOut:
    """Consolida los turnos terminados y emite las alertas pendientes ahora mismo (D19, D20). Idempotente."""
    resultado = ponerse_al_dia(db, reloj, get_settings().zona)
    db.commit()
    return PuestaAlDiaOut(
        consolidados=resultado.consolidados,
        vacantes_sin_cobertura=resultado.vacantes_sin_cobertura,
        alertas=resultado.alertas,
    )
```

En `backend/app/main.py`: importar `coordinacion` y agregar `api.include_router(coordinacion.router)`.

- [ ] **Step 4: Correr y verificar que pasan**

Run: `cd backend && .venv/bin/pytest tests/test_api_consolidacion.py tests/test_api_turnos.py -v`
Expected: PASS (las de `test_api_turnos.py` siguen con el mismo JSON).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/turnos.py backend/app/api/coordinacion.py backend/app/main.py backend/tests/test_api_consolidacion.py
git commit -m "GET /turnos consolida antes de responder y POST /consolidacion la fuerza (D20)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Endpoints de notificaciones

**Files:**
- Create: `backend/app/repos/notificaciones.py`
- Modify: `backend/app/servicios/notificaciones.py` (agregar `marcar_leida`)
- Create: `backend/app/api/notificaciones.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_notificaciones.py`

**Interfaces:**
- Consumes: `notificar` (T3), `emitir_alertas` (T5), `formatear_id_turno`.
- Produces:
  - `listar_de(sesion, usuario_id: int, solo_no_leidas: bool, limite: int) -> list[tuple[Notificacion, int | None, date | None]]` (notificación, `horario_id` y `fecha` de su turno), más nuevas primero.
  - `marcar_leida(sesion, notificacion_id: int, usuario: Usuario, ahora: datetime) -> Notificacion`: 404 `NOTIFICACION_NO_ENCONTRADA` si no existe o es de otro; si ya estaba leída conserva el primer `leida_en`.
  - `GET /api/notificaciones?soloNoLeidas=false` → hasta 50 `NotificacionOut` `{id, tipo, mensaje, turnoId, datos, creadaEn, leidaEn}`; antes emite las alertas pendientes (decisión 7). `POST /api/notificaciones/{id}/leida` → `NotificacionOut`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`backend/tests/test_api_notificaciones.py`:

```python
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.dominio.notificaciones import TipoNotificacion
from app.modelos import RolUsuario
from app.servicios.notificaciones import notificar
from fabricas import abrir_vacante, crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
ANTES = datetime(2026, 10, 12, 8, 0, tzinfo=ZONA)


def test_lista_solo_las_propias_mas_nuevas_primero_con_formato(cliente, sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    beto = crear_usuario(sesion, "Beto")
    turno = guardar_turno(sesion, crear_horario_de_prueba(sesion, ana.id).id, date(2026, 10, 13))
    [vieja] = notificar(sesion, [ana.id], TipoNotificacion.VACANTE_URGENTE, "Vieja", ANTES, turno=turno, datos={"a": 1})
    [nueva] = notificar(sesion, [ana.id], TipoNotificacion.VACANTE_URGENTE, "Nueva", ANTES + timedelta(minutes=30))
    notificar(sesion, [beto.id], TipoNotificacion.VACANTE_URGENTE, "Ajena", ANTES)
    cliente.headers.update(encabezados(ana))

    r = cliente.get("/api/notificaciones")

    assert r.status_code == 200
    assert r.json() == [
        {
            "id": nueva.id,
            "tipo": "VACANTE_URGENTE",
            "mensaje": "Nueva",
            "turnoId": None,
            "datos": {},
            "creadaEn": "2026-10-12T08:30:00-03:00",
            "leidaEn": None,
        },
        {
            "id": vieja.id,
            "tipo": "VACANTE_URGENTE",
            "mensaje": "Vieja",
            "turnoId": f"{turno.horario_id}:2026-10-13",
            "datos": {"a": 1},
            "creadaEn": "2026-10-12T08:00:00-03:00",
            "leidaEn": None,
        },
    ]


def test_marcar_leida_y_filtrar_las_no_leidas(cliente, sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    [leida, pendiente] = [
        notificar(sesion, [ana.id], TipoNotificacion.VACANTE_URGENTE, texto, ANTES)[0] for texto in ("1", "2")
    ]
    cliente.headers.update(encabezados(ana))

    r = cliente.post(f"/api/notificaciones/{leida.id}/leida")
    assert r.status_code == 200
    assert r.json()["leidaEn"] == "2026-10-12T09:00:00-03:00"

    ids = [n["id"] for n in cliente.get("/api/notificaciones", params={"soloNoLeidas": "true"}).json()]
    assert ids == [pendiente.id]


def test_marcar_leida_dos_veces_conserva_la_primera_hora(cliente, sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    [n] = notificar(sesion, [ana.id], TipoNotificacion.VACANTE_URGENTE, "x", ANTES)
    cliente.headers.update(encabezados(ana))
    cliente.post(f"/api/notificaciones/{n.id}/leida")
    reloj.avanzar(timedelta(hours=1))
    assert cliente.post(f"/api/notificaciones/{n.id}/leida").json()["leidaEn"] == "2026-10-12T09:00:00-03:00"


def test_no_se_marca_una_notificacion_ajena(cliente, sesion, reloj):
    # Review Focus 5: mismo 404 que una inexistente.
    ana = crear_usuario(sesion, "Ana")
    beto = crear_usuario(sesion, "Beto")
    [ajena] = notificar(sesion, [beto.id], TipoNotificacion.VACANTE_URGENTE, "x", ANTES)
    cliente.headers.update(encabezados(ana))
    for notificacion_id in (ajena.id, 999999):
        r = cliente.post(f"/api/notificaciones/{notificacion_id}/leida")
        assert r.status_code == 404
        assert r.json()["codigo"] == "NOTIFICACION_NO_ENCONTRADA"
    assert ajena.leida_en is None


def test_devuelve_como_maximo_50(cliente, sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    for i in range(51):
        notificar(sesion, [ana.id], TipoNotificacion.VACANTE_URGENTE, str(i), ANTES + timedelta(seconds=i))
    cliente.headers.update(encabezados(ana))
    respuesta = cliente.get("/api/notificaciones").json()
    assert len(respuesta) == 50
    assert respuesta[0]["mensaje"] == "50"


def test_consultar_emite_las_alertas_pendientes(cliente, sesion, reloj):
    ana = crear_usuario(sesion, "Ana")
    enzo = crear_usuario(sesion, "Enzo", rol=RolUsuario.COORDINADOR)
    turno = guardar_turno(sesion, crear_horario_de_prueba(sesion, ana.id).id, date(2026, 10, 13))
    abrir_vacante(sesion, turno, ana.id, datetime(2026, 10, 9, tzinfo=ZONA))
    cliente.headers.update(encabezados(enzo))

    [alerta] = cliente.get("/api/notificaciones").json()

    assert alerta["tipo"] == "ALERTA_SIN_COBERTURA"
    assert alerta["datos"] == {"umbral": "24H"}
    assert alerta["turnoId"] == f"{turno.horario_id}:2026-10-13"


def test_sin_sesion_responde_401(cliente):
    assert cliente.get("/api/notificaciones").status_code == 401
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && .venv/bin/pytest tests/test_api_notificaciones.py -v`
Expected: FAIL con 404 en `/api/notificaciones`.

- [ ] **Step 3: Implementar**

`backend/app/repos/notificaciones.py`:

```python
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import Notificacion, Turno


def listar_de(
    sesion: Session, usuario_id: int, solo_no_leidas: bool, limite: int
) -> list[tuple[Notificacion, int | None, date | None]]:
    """Notificaciones del usuario, más nuevas primero, con el horario y la fecha de su turno (para el id de D09)."""
    consulta = (
        select(Notificacion, Turno.horario_id, Turno.fecha)
        .outerjoin(Turno, Notificacion.turno_id == Turno.id)
        .where(Notificacion.usuario_id == usuario_id)
    )
    if solo_no_leidas:
        consulta = consulta.where(Notificacion.leida_en.is_(None))
    consulta = consulta.order_by(Notificacion.creada_en.desc(), Notificacion.id.desc()).limit(limite)
    return [tuple(fila) for fila in sesion.execute(consulta).all()]
```

Agregar a `backend/app/servicios/notificaciones.py` (importar `ErrorDominio`):

```python
def marcar_leida(sesion: Session, notificacion_id: int, usuario: Usuario, ahora: datetime) -> Notificacion:
    """Marca como leída una notificación propia. Una ajena responde igual que una inexistente."""
    notificacion = sesion.scalar(
        select(Notificacion)
        .where(Notificacion.id == notificacion_id, Notificacion.usuario_id == usuario.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if notificacion is None:
        raise ErrorDominio("NOTIFICACION_NO_ENCONTRADA", "La notificación no existe.", 404)
    if notificacion.leida_en is None:
        notificacion.leida_en = ahora
        sesion.flush()
    return notificacion
```

`backend/app/api/notificaciones.py`:

```python
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.esquemas import Esquema
from app.auth import usuario_actual
from app.config import get_settings
from app.db import get_db
from app.dominio.calendario import formatear_id_turno
from app.modelos import Notificacion, Turno, Usuario
from app.reloj import Reloj, get_reloj
from app.repos.notificaciones import listar_de
from app.servicios.alertas import emitir_alertas
from app.servicios.notificaciones import marcar_leida

router = APIRouter()

LIMITE = 50


class NotificacionOut(Esquema):
    id: int
    tipo: str
    mensaje: str
    turno_id: str | None
    datos: dict[str, Any]
    creada_en: datetime
    leida_en: datetime | None


def _a_salida(notificacion: Notificacion, horario_id: int | None, fecha: date | None) -> NotificacionOut:
    zona = get_settings().zona
    return NotificacionOut(
        id=notificacion.id,
        tipo=notificacion.tipo,
        mensaje=notificacion.mensaje,
        turno_id=formatear_id_turno(horario_id, fecha) if horario_id is not None else None,
        datos=notificacion.datos,
        creada_en=notificacion.creada_en.astimezone(zona),
        leida_en=notificacion.leida_en.astimezone(zona) if notificacion.leida_en else None,
    )


@router.get("/notificaciones", response_model=list[NotificacionOut])
def listar(
    solo_no_leidas: bool = Query(False, alias="soloNoLeidas"),
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    usuario: Usuario = Depends(usuario_actual),
) -> list[NotificacionOut]:
    """Avisos dentro de la app (D05), más nuevos primero, hasta 50. La interfaz consulta cada 10 a 15 s.

    Antes de responder emite las alertas de D19 que vencieron: así llegan a tiempo sin proceso programado.
    """
    emitir_alertas(db, reloj, get_settings().zona)
    db.commit()
    return [_a_salida(*fila) for fila in listar_de(db, usuario.id, solo_no_leidas, LIMITE)]


@router.post("/notificaciones/{notificacion_id}/leida", response_model=NotificacionOut)
def leida(
    notificacion_id: int,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    usuario: Usuario = Depends(usuario_actual),
) -> NotificacionOut:
    notificacion = marcar_leida(db, notificacion_id, usuario, reloj.ahora())
    db.commit()
    turno = db.get(Turno, notificacion.turno_id) if notificacion.turno_id is not None else None
    return _a_salida(notificacion, turno.horario_id if turno else None, turno.fecha if turno else None)
```

En `backend/app/main.py`: importar `notificaciones` y agregar `api.include_router(notificaciones.router)`.

- [ ] **Step 4: Correr y verificar que pasan**

Run: `cd backend && .venv/bin/pytest tests/test_api_notificaciones.py tests/test_notificaciones.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repos/notificaciones.py backend/app/servicios/notificaciones.py backend/app/api/notificaciones.py backend/app/main.py backend/tests/test_api_notificaciones.py
git commit -m "GET /notificaciones (emite las alertas vencidas) y POST /notificaciones/{id}/leida (D05, D19)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Turno sin cobertura

**Files:**
- Create: `backend/app/servicios/sin_cobertura.py`
- Modify: `backend/app/api/coordinacion.py`
- Test: `backend/tests/test_api_sin_cobertura.py`

**Interfaces:**
- Consumes: `parsear_id_turno`, `calcular_turnos`, `versiones_en_rango`, `consolidar_pendientes` (para la prueba de consolidación posterior).
- Produces: `marcar_sin_cobertura(sesion: Session, turno_id: str, actor: Usuario, reloj: Reloj, zona: ZoneInfo) -> tuple[Turno, Vacante]`. Orden de chequeo: turno sin fila → 404 `TURNO_NO_ENCONTRADO` si la plantilla no lo produce, si no 409 `TURNO_SIN_VACANTE`; 409 `TURNO_CONSOLIDADO`; 409 `YA_SIN_COBERTURA`; 409 `TURNO_SIN_VACANTE`; 422 `TURNO_NO_EMPEZO`. Efecto: vacante `SIN_COBERTURA` con `cerrada_en`, `turno.sin_cobertura_en`, evento `TURNO_SIN_COBERTURA` con `actor_id` del coordinador y `datos = {"vacante_id": id}`. Endpoint `POST /api/turnos/{turnoId}/sin-cobertura` (solo coordinadores) → `{"turnoId", "sinCoberturaEn", "vacanteId"}`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`backend/tests/test_api_sin_cobertura.py`:

```python
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.modelos import EstadoVacante, EventoTurno, TipoEventoTurno, Turno
from app.servicios.consolidacion import consolidar_pendientes
from fabricas import abrir_vacante, crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


@pytest.fixture
def turno_con_vacante(sesion, como_coordinador, reloj):
    ana = crear_usuario(sesion, "Ana")
    turno = guardar_turno(sesion, crear_horario_de_prueba(sesion, ana.id).id, date(2026, 10, 13))
    vacante = abrir_vacante(sesion, turno, ana.id, datetime(2026, 10, 9, tzinfo=ZONA))
    reloj.avanzar(timedelta(days=1, minutes=30))  # martes 13/10 09:30: el turno empezó
    return turno, vacante


def ruta(turno):
    return f"/api/turnos/{turno.horario_id}:{turno.fecha.isoformat()}/sin-cobertura"


def test_el_coordinador_marca_el_turno_sin_cobertura(cliente, sesion, como_coordinador, reloj, turno_con_vacante):
    turno, vacante = turno_con_vacante

    r = cliente.post(ruta(turno))

    assert r.status_code == 200
    assert r.json() == {
        "turnoId": f"{turno.horario_id}:2026-10-13",
        "sinCoberturaEn": "2026-10-13T09:30:00-03:00",
        "vacanteId": vacante.id,
    }
    assert vacante.estado == EstadoVacante.SIN_COBERTURA
    assert vacante.cerrada_en == reloj.ahora()
    assert turno.sin_cobertura_en == reloj.ahora()
    evento = sesion.scalars(select(EventoTurno).where(EventoTurno.turno_id == turno.id)).one()
    assert evento.tipo == TipoEventoTurno.TURNO_SIN_COBERTURA
    assert evento.actor_id == como_coordinador.id
    assert evento.datos == {"vacante_id": vacante.id}


def test_al_consolidar_queda_sin_realizador(cliente, sesion, reloj, turno_con_vacante):
    turno, _ = turno_con_vacante
    cliente.post(ruta(turno))
    reloj.avanzar(timedelta(hours=11))
    consolidar_pendientes(sesion, reloj, ZONA)
    assert turno.consolidado_en is not None
    assert turno.realizador_id is None


def test_antes_del_inicio_responde_422(cliente, reloj, turno_con_vacante):
    turno, _ = turno_con_vacante
    reloj.avanzar(timedelta(hours=-2))
    r = cliente.post(ruta(turno))
    assert r.status_code == 422
    assert r.json()["codigo"] == "TURNO_NO_EMPEZO"


def test_dos_veces_responde_409(cliente, turno_con_vacante):
    turno, _ = turno_con_vacante
    cliente.post(ruta(turno))
    r = cliente.post(ruta(turno))
    assert r.status_code == 409
    assert r.json()["codigo"] == "YA_SIN_COBERTURA"


def test_turno_consolidado_responde_409(cliente, sesion, reloj, turno_con_vacante):
    turno, _ = turno_con_vacante
    turno.consolidado_en = reloj.ahora()
    sesion.flush()
    r = cliente.post(ruta(turno))
    assert r.status_code == 409
    assert r.json()["codigo"] == "TURNO_CONSOLIDADO"


def test_turno_guardado_sin_vacante_responde_409(cliente, sesion, como_coordinador, reloj):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id)
    turno = guardar_turno(sesion, horario.id, date(2026, 10, 13))
    reloj.avanzar(timedelta(days=1))
    r = cliente.post(ruta(turno))
    assert r.status_code == 409
    assert r.json()["codigo"] == "TURNO_SIN_VACANTE"


def test_turno_calculado_sin_vacante_responde_409_y_no_guarda_nada(cliente, sesion, como_coordinador, reloj):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id)
    reloj.avanzar(timedelta(days=1))
    r = cliente.post(f"/api/turnos/{horario.id}:2026-10-13/sin-cobertura")
    assert r.status_code == 409
    assert r.json()["codigo"] == "TURNO_SIN_VACANTE"
    assert sesion.scalar(select(func.count()).select_from(Turno)) == 0


def test_turno_que_no_existe_responde_404(cliente, sesion, como_coordinador):
    horario = crear_horario_de_prueba(sesion, crear_usuario(sesion, "Ana").id)
    r = cliente.post(f"/api/turnos/{horario.id}:2026-10-14/sin-cobertura")  # miércoles: el horario es de martes
    assert r.status_code == 404
    assert r.json()["codigo"] == "TURNO_NO_ENCONTRADO"


def test_un_medico_no_marca_sin_cobertura(cliente, sesion, turno_con_vacante):
    turno, vacante = turno_con_vacante
    cliente.headers.update(encabezados(crear_usuario(sesion, "Beto")))
    r = cliente.post(ruta(turno))
    assert r.status_code == 403
    assert vacante.estado == EstadoVacante.ABIERTA
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && .venv/bin/pytest tests/test_api_sin_cobertura.py -v`
Expected: FAIL con 404/405 en la ruta.

- [ ] **Step 3: Implementar**

`backend/app/servicios/sin_cobertura.py`:

```python
"""Turno sin cobertura (D19): el coordinador lo marca cuando la vacante sigue abierta al llegar el inicio."""

from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dominio.calendario import calcular_turnos, parsear_id_turno
from app.errores import ErrorDominio
from app.modelos import EstadoVacante, EventoTurno, TipoEventoTurno, Turno, Usuario, Vacante
from app.reloj import Reloj
from app.repos.horarios import versiones_en_rango


def marcar_sin_cobertura(
    sesion: Session, turno_id: str, actor: Usuario, reloj: Reloj, zona: ZoneInfo
) -> tuple[Turno, Vacante]:
    """Cierra la vacante como SIN_COBERTURA y lo registra en la bitácora (D19, D22). No hace commit."""
    horario_id, fecha = parsear_id_turno(turno_id)
    turno = sesion.scalar(
        select(Turno)
        .where(Turno.horario_id == horario_id, Turno.fecha == fecha)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if turno is None:
        # Sin fila no hay vacante (D11); solo falta distinguir un turno inexistente.
        existe = any(t.horario_id == horario_id and t.fecha == fecha
                     for t in calcular_turnos(versiones_en_rango(sesion, fecha, fecha), fecha, fecha, zona))
        if not existe:
            raise ErrorDominio("TURNO_NO_ENCONTRADO", f"No existe el turno {turno_id}.", 404)
        raise ErrorDominio("TURNO_SIN_VACANTE", "El turno no tiene una vacante abierta.", 409)
    if turno.consolidado_en is not None:
        raise ErrorDominio("TURNO_CONSOLIDADO", "El turno ya terminó y se consolidó.", 409)
    if turno.sin_cobertura_en is not None:
        raise ErrorDominio("YA_SIN_COBERTURA", "El turno ya está marcado sin cobertura.", 409)
    vacante = sesion.scalar(
        select(Vacante)
        .where(Vacante.turno_id == turno.id, Vacante.estado == EstadoVacante.ABIERTA)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if vacante is None:
        raise ErrorDominio("TURNO_SIN_VACANTE", "El turno no tiene una vacante abierta.", 409)
    ahora = reloj.ahora()
    if ahora < turno.inicio:
        raise ErrorDominio("TURNO_NO_EMPEZO", "Un turno se marca sin cobertura cuando ya empezó (D19).")
    vacante.estado = EstadoVacante.SIN_COBERTURA
    vacante.cerrada_en = ahora
    turno.sin_cobertura_en = ahora
    sesion.add(
        EventoTurno(
            turno_id=turno.id,
            tipo=TipoEventoTurno.TURNO_SIN_COBERTURA,
            actor_id=actor.id,
            ocurrido_en=ahora,
            datos={"vacante_id": vacante.id},
        )
    )
    sesion.flush()
    return turno, vacante
```

Agregar a `backend/app/api/coordinacion.py` (imports: `datetime`, `formatear_id_turno`, `marcar_sin_cobertura`):

```python
class SinCoberturaOut(Esquema):
    turno_id: str
    sin_cobertura_en: datetime
    vacante_id: int


@router.post("/turnos/{turno_id}/sin-cobertura", response_model=SinCoberturaOut)
def sin_cobertura(
    turno_id: str,
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    coordinador: Usuario = Depends(requiere_coordinador),
) -> SinCoberturaOut:
    """Nadie cubre la vacante y el turno ya empezó: se consolidará sin realizador (D19)."""
    zona = get_settings().zona
    turno, vacante = marcar_sin_cobertura(db, turno_id, coordinador, reloj, zona)
    db.commit()
    return SinCoberturaOut(
        turno_id=formatear_id_turno(turno.horario_id, turno.fecha),
        sin_cobertura_en=turno.sin_cobertura_en.astimezone(zona),
        vacante_id=vacante.id,
    )
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `cd backend && .venv/bin/pytest tests/test_api_sin_cobertura.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/servicios/sin_cobertura.py backend/app/api/coordinacion.py backend/tests/test_api_sin_cobertura.py
git commit -m "POST /turnos/{id}/sin-cobertura cierra la vacante y lo registra en la bitácora (D19, D22)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Indicador de horas sin cobertura por mes

**Files:**
- Create: `backend/app/dominio/indicadores.py`
- Create: `backend/app/repos/indicadores.py`
- Modify: `backend/app/api/coordinacion.py`
- Test: `backend/tests/test_indicadores.py`, `backend/tests/test_api_indicadores.py`

**Interfaces:**
- Consumes: `consolidar_pendientes` (T4).
- Produces: `meses_del_rango(desde: str, hasta: str) -> list[str]` (422 `RANGO_INVALIDO`, 422 `RANGO_DEMASIADO_GRANDE` con más de `MAX_MESES = 24`); `sin_cobertura_por_mes(sesion, desde: date, hasta_exclusive: date) -> dict[str, tuple[float, int]]`. Endpoint `GET /api/indicadores/sin-cobertura?desde=AAAA-MM&hasta=AAAA-MM` (solo coordinadores) → `[{"mes": "2026-10", "horas": 24.0, "turnos": 2}, ...]` con todos los meses del rango.

- [ ] **Step 1: Escribir las pruebas que fallan**

`backend/tests/test_indicadores.py`:

```python
import pytest

from app.dominio.indicadores import meses_del_rango
from app.errores import ErrorDominio


def test_meses_del_rango_cruza_el_anio():
    assert meses_del_rango("2026-11", "2027-02") == ["2026-11", "2026-12", "2027-01", "2027-02"]


def test_un_solo_mes():
    assert meses_del_rango("2026-10", "2026-10") == ["2026-10"]


def test_hasta_anterior_es_rango_invalido():
    with pytest.raises(ErrorDominio) as error:
        meses_del_rango("2026-10", "2026-09")
    assert error.value.codigo == "RANGO_INVALIDO"


def test_mas_de_24_meses_es_demasiado():
    assert len(meses_del_rango("2025-01", "2026-12")) == 24
    with pytest.raises(ErrorDominio) as error:
        meses_del_rango("2025-01", "2027-01")
    assert error.value.codigo == "RANGO_DEMASIADO_GRANDE"
```

`backend/tests/test_api_indicadores.py`:

```python
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from fabricas import abrir_vacante, crear_horario_de_prueba, crear_usuario, encabezados, guardar_turno

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def test_horas_sin_cobertura_por_mes(cliente, sesion, como_coordinador):
    ana = crear_usuario(sesion, "Ana")
    con_titular = crear_horario_de_prueba(sesion, ana.id)  # martes 08 a 20: lo hace Ana, no cuenta
    crear_horario_de_prueba(sesion, None)  # martes 08 a 20 sin titular (BAJA): 12 h cada martes
    turno = guardar_turno(sesion, con_titular.id, date(2026, 10, 6))
    abrir_vacante(sesion, turno, ana.id, datetime(2026, 10, 1, tzinfo=ZONA))  # quedó abierta al terminar

    r = cliente.get("/api/indicadores/sin-cobertura", params={"desde": "2026-09", "hasta": "2026-11"})

    assert r.status_code == 200
    assert r.json() == [
        {"mes": "2026-09", "horas": 48.0, "turnos": 4},
        {"mes": "2026-10", "horas": 24.0, "turnos": 2},
        {"mes": "2026-11", "horas": 0.0, "turnos": 0},
    ]


@pytest.mark.parametrize(
    "desde,hasta,codigo",
    [
        ("2026-10", "2026-09", "RANGO_INVALIDO"),
        ("2024-01", "2026-12", "RANGO_DEMASIADO_GRANDE"),
        ("2026-13", "2026-12", "VALIDACION"),
        ("0000-01", "0000-02", "VALIDACION"),
    ],
)
def test_rangos_invalidos_son_422(cliente, como_coordinador, desde, hasta, codigo):
    r = cliente.get("/api/indicadores/sin-cobertura", params={"desde": desde, "hasta": hasta})
    assert r.status_code == 422
    assert r.json()["codigo"] == codigo


def test_un_medico_no_ve_el_indicador(cliente, sesion, reloj):
    cliente.headers.update(encabezados(crear_usuario(sesion, "Ana")))
    r = cliente.get("/api/indicadores/sin-cobertura", params={"desde": "2026-10", "hasta": "2026-10"})
    assert r.status_code == 403
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && .venv/bin/pytest tests/test_indicadores.py tests/test_api_indicadores.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.dominio.indicadores'`.

- [ ] **Step 3: Implementar**

`backend/app/dominio/indicadores.py`:

```python
"""Rango de meses del indicador de horas sin cobertura (D19). Lógica pura: sin base de datos ni FastAPI."""

from datetime import date

from app.errores import ErrorDominio

MAX_MESES = 24


def _indice(mes: str) -> int:
    anio, numero = mes.split("-")
    return int(anio) * 12 + int(numero) - 1


def _mes(indice: int) -> str:
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def meses_del_rango(desde: str, hasta: str) -> list[str]:
    """Meses "AAAA-MM" de desde a hasta, inclusive. Los formatos ya los validó la API."""
    inicio, fin = _indice(desde), _indice(hasta)
    if fin < inicio:
        raise ErrorDominio("RANGO_INVALIDO", "El mes 'hasta' no puede ser anterior a 'desde'.")
    if fin - inicio + 1 > MAX_MESES:
        raise ErrorDominio("RANGO_DEMASIADO_GRANDE", f"El rango no puede superar {MAX_MESES} meses.")
    return [_mes(i) for i in range(inicio, fin + 1)]


def primer_dia(mes: str) -> date:
    return date(int(mes[:4]), int(mes[5:]), 1)


def primer_dia_siguiente(mes: str) -> date:
    return primer_dia(_mes(_indice(mes) + 1))
```

`backend/app/repos/indicadores.py`:

```python
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modelos import Turno


def sin_cobertura_por_mes(sesion: Session, desde: date, hasta_exclusive: date) -> dict[str, tuple[float, int]]:
    """Horas y cantidad de turnos consolidados sin realizador, por mes de la fecha de inicio (D13, D19, D24)."""
    mes = func.to_char(Turno.fecha, "YYYY-MM")
    consulta = (
        select(mes, func.sum(func.extract("epoch", Turno.fin - Turno.inicio)), func.count())
        .where(
            Turno.consolidado_en.is_not(None),
            Turno.realizador_id.is_(None),
            Turno.fecha >= desde,
            Turno.fecha < hasta_exclusive,
        )
        .group_by(mes)
    )
    return {fila[0]: (round(float(fila[1]) / 3600, 1), fila[2]) for fila in sesion.execute(consulta).all()}
```

Agregar a `backend/app/api/coordinacion.py` (imports: `Query`, `meses_del_rango`, `primer_dia`, `primer_dia_siguiente`, `sin_cobertura_por_mes`, `consolidar_pendientes`):

```python
PATRON_MES = r"^(19|20)\d{2}-(0[1-9]|1[0-2])$"


class IndicadorMesOut(Esquema):
    mes: str
    horas: float
    turnos: int


@router.get("/indicadores/sin-cobertura", response_model=list[IndicadorMesOut])
def indicador_sin_cobertura(
    desde: str = Query(pattern=PATRON_MES),
    hasta: str = Query(pattern=PATRON_MES),
    db: Session = Depends(get_db),
    reloj: Reloj = Depends(get_reloj),
    _coordinador: Usuario = Depends(requiere_coordinador),
) -> list[IndicadorMesOut]:
    """Horas sin cobertura por mes (D19): turnos consolidados sin realizador, incluidos los BAJA sin cubrir (D24)."""
    meses = meses_del_rango(desde, hasta)
    consolidar_pendientes(db, reloj, get_settings().zona)
    db.commit()
    datos = sin_cobertura_por_mes(db, primer_dia(meses[0]), primer_dia_siguiente(meses[-1]))
    return [IndicadorMesOut(mes=mes, horas=datos.get(mes, (0.0, 0))[0], turnos=datos.get(mes, (0.0, 0))[1]) for mes in meses]
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `cd backend && .venv/bin/pytest tests/test_indicadores.py tests/test_api_indicadores.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/dominio/indicadores.py backend/app/repos/indicadores.py backend/app/api/coordinacion.py backend/tests/test_indicadores.py backend/tests/test_api_indicadores.py
git commit -m "GET /indicadores/sin-cobertura: horas sin cobertura por mes (D19, D24)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Documentación y suite completa

**Files:**
- Modify: `backend/CLAUDE.md`, `docs/prompts-principales.md`

- [ ] **Step 1: Actualizar `backend/CLAUDE.md`**

En "Estructura", punto 7 (reloj), agregar: "En modo demo (`MODO_DEMO=true`) `get_reloj` suma el desfase que fija `POST /api/demo/reloj` (en memoria: reiniciar el servidor vuelve a la hora real). Después de `scripts.seed`, volver a la hora real con `{"ahora": null}`."

En "Convenciones", agregar:

```markdown
16. Consolidación perezosa (D20): `ponerse_al_dia(sesion, reloj, zona)` de `app/servicios/consolidacion.py` consolida y emite alertas dentro de la transacción de quien llama; lo usan `GET /turnos` y `POST /consolidacion` (y `GET /indicadores/sin-cobertura` consolida). `GET /notificaciones` solo emite alertas. La marca `consolidacion_estado` se bloquea en cada consolidación y el seed la vacía.
17. Notificaciones: crearlas siempre con `notificar(...)` de `app/servicios/notificaciones.py`, en la transacción de la acción (D22), y elegir destinatarios con `destinatarios(sesion, rol, hoy(reloj), excepto=...)`. Los tipos están en `TipoNotificacion` (`app/dominio/notificaciones.py`).
18. Orden de bloqueos completo: `usuario`, `horario_pactado`, `consolidacion_estado`, `turno`, `vacante`.
```

- [ ] **Step 2: Registrar el prompt en `docs/prompts-principales.md`**

Agregar al final una sección con el formato de las anteriores: fecha 8/10/2026, herramienta Claude Code con Superpowers, objetivo "F4 historia y alertas, backend", el pedido original completo (punto 2 del pedido de Florencia), resultado: este plan y la branch `feature/f4-historia-alertas`. Las decisiones propias del plan (sección "Decisiones de este plan") se copian a `docs/bitacora-de-desvios.md` al abrir el PR.

- [ ] **Step 3: Correr la suite completa**

Run: `docker compose up -d --wait && cd backend && .venv/bin/pytest -q`
Expected: PASS, sin pruebas omitidas por falta de base.

- [ ] **Step 4: Probar a mano con el seed (base local)**

```bash
cd backend
DATABASE_URL=postgresql://guardia:guardia@localhost:5433/guardia .venv/bin/alembic upgrade head
DATABASE_URL=postgresql://guardia:guardia@localhost:5433/guardia .venv/bin/python -m scripts.seed --confirmar
DATABASE_URL=postgresql://guardia:guardia@localhost:5433/guardia MODO_DEMO=true .venv/bin/uvicorn app.main:app --port 8000
```

Verificar en `/docs` que aparecen `POST /api/consolidacion`, `POST /api/turnos/{turno_id}/sin-cobertura`, `GET /api/indicadores/sin-cobertura`, `GET /api/notificaciones`, `POST /api/notificaciones/{notificacion_id}/leida` y `POST /api/demo/reloj`; sin `MODO_DEMO`, el último no aparece. Nunca correr el seed ni la migración contra Supabase en este paso.

- [ ] **Step 5: Commit**

```bash
git add backend/CLAUDE.md docs/prompts-principales.md
git commit -m "Documentar consolidación, notificaciones y reloj de demo de F4

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Después: pushear la branch y abrir el PR contra `main` con la sección de desvíos (decisiones de este plan) y el aviso a Mariano de "Coordinación con Mariano". No mergear.

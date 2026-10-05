# F0 + F1: esqueleto, plantilla y calendario. Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** dejar funcionando el esqueleto de Guardia Viva (FastAPI + Postgres + React mínimo + pruebas contra Postgres) y el cálculo de turnos desde la plantilla, expuesto en `GET /api/turnos`.

**Arquitectura:** backend FastAPI en capas finas: `dominio/` tiene lógica pura sin base ni FastAPI, `repos/` tiene las consultas SQLAlchemy y `api/` los routers. El cálculo de turnos es una función pura que recibe versiones de horario y un rango de fechas. El esquema se crea con una migración de Alembic escrita a mano en SQL (extensión `btree_gist`, columna generada, exclusión de vigencias, RLS). Las pruebas corren contra Postgres 15 en docker-compose, dentro de una transacción que se deshace, salvo las marcadas `commit_real`.

**Tecnologías:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, pydantic-settings, pytest, httpx; React + Vite (JavaScript), Playwright (`@playwright/test`).

**Spec:** `docs/superpowers/specs/2026-10-05-f0-f1-esqueleto-plantilla-calendario-design.md`

## Restricciones globales

- Toda la API va bajo el prefijo `/api`. El OpenAPI sigue en `/docs`.
- Los errores tienen formato único `{"codigo": "...", "mensaje": "..."}`. Los errores de validación de FastAPI salen con `codigo: "VALIDACION"` y status 422.
- JSON en camelCase mediante alias de Pydantic (`horarioId`, `duracionHoras`).
- Zona horaria del servicio: `America/Argentina/Buenos_Aires`. Todo instante con zona horaria.
- Nada en `backend/app/` consulta la hora del sistema fuera de `app/reloj.py` (D27).
- Día de la semana ISO: 1 = lunes … 7 = domingo.
- Vigencias semiabiertas `[vigente_desde, vigente_hasta)`; `vigente_hasta` vacío significa vigente.
- Duración en horas enteras de 1 a 24; hora de inicio `TIME` con minutos.
- Id de turno `"horarioId:fecha"`, por ejemplo `"7:2026-10-17"` (D09).
- Rango máximo de `GET /api/turnos`: 62 días.
- Pruebas siempre contra Postgres (nunca SQLite); la base de prueba es el contenedor local de docker-compose (puerto 5433).
- Entorno de Python: `venv` + `pip` con `pyproject.toml`. Todos los comandos del backend se corren desde `backend/`.
- Commits chicos, en español, con la decisión citada cuando corresponda. Cada commit termina con la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Los subagentes que implementan usan Sonnet.
- Playwright y lo que necesite se instala como dependencia de desarrollo del frontend.

## Foco de revisión

Casos que el spec implica y que los revisores deben vigilar; cada uno tiene su prueba en la tarea indicada.

1. **Desplazamiento horario en el JSON:** `inicio` y `fin` deben salir con `-03:00`, no en UTC ni sin zona. Prueba en la tarea 6 (`test_turnos_formato_exacto`).
2. **Borde del rango máximo:** 62 días se aceptan y 63 se rechazan con `RANGO_DEMASIADO_GRANDE`. Prueba en la tarea 6 (`test_rango_de_62_dias_se_acepta_y_63_no`).
3. **Horario sin titular en la API:** debe salir `"titular": null`, no un error ni un objeto vacío. Prueba en la tarea 6 (`test_horario_sin_titular_sale_con_titular_null`).
4. **Fecha imposible en la consulta** (`2026-02-30`): 422 `VALIDACION` con el formato de error, no 500. Prueba en la tarea 6 (`test_fecha_imposible_es_error_de_validacion`).
5. **Pruebas apuntando a una base remota:** si `TEST_DATABASE_URL` apunta a Supabase por error, la infraestructura de pruebas borraría esa base. Debe negarse. Prueba en la tarea 2 (`test_verificar_base_local_rechaza_host_remoto`).

---

## Estructura de archivos

```
.gitignore                                   (T1)
docker-compose.yml                           (T2)
backend/
  pyproject.toml                             (T1)
  .env.example                               (T1)
  CLAUDE.md                                  (T9)
  alembic.ini                                (T2)
  migrations/env.py, script.py.mako          (T2)
  migrations/versions/0001_usuarios_y_plantilla.py   (T4)
  app/__init__.py                            (T1)
  app/config.py                              (T1)  Settings, get_settings
  app/reloj.py                               (T1)  Reloj, RelojSistema, RelojFijo, get_reloj
  app/errores.py                             (T1)  ErrorDominio (pura, sin FastAPI)
  app/auth.py                                (T6)  usuario_actual (enganche para F5)
  app/main.py                                (T1, T2, T6)  crear_app, app
  app/db.py                                  (T2)  engine, SessionLocal, get_db
  app/api/__init__.py                        (T1)
  app/api/manejadores.py                     (T1)  registrar_manejadores
  app/api/health.py                          (T2)
  app/api/turnos.py                          (T6)
  app/dominio/__init__.py                    (T3)
  app/dominio/calendario.py                  (T3)
  app/modelos/__init__.py                    (T2, T4)
  app/modelos/base.py                        (T2)
  app/modelos/usuario.py                     (T4)
  app/modelos/horario.py                     (T4)
  app/repos/__init__.py                      (T5)
  app/repos/horarios.py                      (T5)
  scripts/__init__.py, scripts/seed.py       (T7)
  tests/conftest.py                          (T2)
  tests/fabricas.py                          (T4)
  tests/test_*.py                            (cada tarea)
frontend/                                    (T8)
CLAUDE.md, docs/...                          (T9)
```

Una diferencia menor con el spec: el spec ubica en `errores.py` tanto la excepción como el formato. El plan deja en `app/errores.py` solo `ErrorDominio`, sin importar nada de FastAPI, y pone los manejadores HTTP en `app/api/manejadores.py`. Así `dominio/` puede lanzar `ErrorDominio` y seguir libre de FastAPI.

---

### Tarea 1: proyecto backend, configuración, reloj y formato de errores

**Archivos:**
- Crear: `.gitignore`, `backend/pyproject.toml`, `backend/.env.example`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/reloj.py`, `backend/app/errores.py`, `backend/app/api/__init__.py`, `backend/app/api/manejadores.py`, `backend/app/main.py`
- Pruebas: `backend/tests/test_config.py`, `backend/tests/test_reloj.py`, `backend/tests/test_errores.py`, `backend/tests/test_sin_hora_del_sistema.py`

**Interfaces:**
- Consume: nada.
- Produce:
  - `app.config.Settings` con `database_url: str`, `test_database_url: str`, `app_timezone: str`, `modo_demo: bool` y la propiedad `zona -> ZoneInfo`.
  - `app.config.get_settings() -> Settings`, cacheada.
  - `app.reloj.Reloj` (protocolo con `ahora() -> datetime`), `RelojSistema(zona)`, `RelojFijo(instante)` con `avanzar(timedelta)`, y `get_reloj() -> Reloj`.
  - `app.errores.ErrorDominio(codigo: str, mensaje: str, status: int = 422)`.
  - `app.api.manejadores.registrar_manejadores(app: FastAPI) -> None`.
  - `app.main.crear_app() -> FastAPI` y `app.main.app`.

- [ ] **Paso 1: crear `.gitignore` en la raíz**

```gitignore
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
node_modules/
dist/
test-results/
playwright-report/
```

- [ ] **Paso 2: crear `backend/pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "guardia-viva-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy>=2.0.30",
  "alembic>=1.13",
  "psycopg[binary]>=3.2",
  "pydantic-settings>=2.4",
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "httpx>=0.27"]

[tool.setuptools.packages.find]
include = ["app*", "scripts*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--strict-markers"
markers = [
  "commit_real: la prueba confirma transacciones reales (no se deshace); la base se vacía al terminar",
]
```

- [ ] **Paso 3: crear `backend/.env.example`**

```dotenv
# Copiar a .env y completar. El archivo .env no se versiona.
# Desarrollo y demo: Supabase, cadena del Session pooler
# (Project Settings > Database > Connection string > Session pooler).
# Sin .env, el backend usa el Postgres local de docker-compose.
DATABASE_URL=postgresql://guardia:guardia@localhost:5433/guardia
# Pruebas: siempre el Postgres local de docker-compose. Nunca Supabase.
TEST_DATABASE_URL=postgresql://guardia:guardia@localhost:5433/guardia_test
APP_TIMEZONE=America/Argentina/Buenos_Aires
MODO_DEMO=false
```

- [ ] **Paso 4: crear el entorno e instalar**

Run (desde `backend/`): `python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"`
Expected: termina sin errores.

Crear vacíos `backend/app/__init__.py` y `backend/app/api/__init__.py`.

- [ ] **Paso 5: escribir las pruebas que fallan**

`backend/tests/test_config.py`:

```python
from app.config import Settings


def test_normaliza_url_postgresql_al_driver_psycopg():
    s = Settings(database_url="postgresql://u:p@host:5432/db", _env_file=None)
    assert s.database_url == "postgresql+psycopg://u:p@host:5432/db"


def test_normaliza_url_postgres_corta():
    s = Settings(test_database_url="postgres://u:p@localhost:5433/t", _env_file=None)
    assert s.test_database_url == "postgresql+psycopg://u:p@localhost:5433/t"


def test_respeta_url_que_ya_tiene_driver():
    s = Settings(database_url="postgresql+psycopg://u:p@h/db", _env_file=None)
    assert s.database_url == "postgresql+psycopg://u:p@h/db"


def test_zona_por_defecto_es_buenos_aires():
    s = Settings(_env_file=None)
    assert s.zona.key == "America/Argentina/Buenos_Aires"
```

`backend/tests/test_reloj.py`:

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.reloj import RelojFijo, RelojSistema

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def test_reloj_fijo_devuelve_el_instante_dado():
    instante = datetime(2026, 10, 12, 9, 0, tzinfo=ZONA)
    assert RelojFijo(instante).ahora() == instante


def test_reloj_fijo_avanza():
    reloj = RelojFijo(datetime(2026, 10, 12, 9, 0, tzinfo=ZONA))
    reloj.avanzar(timedelta(hours=26))
    assert reloj.ahora() == datetime(2026, 10, 13, 11, 0, tzinfo=ZONA)


def test_reloj_fijo_rechaza_instante_sin_zona():
    with pytest.raises(ValueError):
        RelojFijo(datetime(2026, 10, 12, 9, 0))


def test_reloj_sistema_devuelve_hora_con_zona_del_servicio():
    ahora = RelojSistema(ZONA).ahora()
    assert ahora.tzinfo is not None
    assert ahora.utcoffset() == timedelta(hours=-3)
```

`backend/tests/test_errores.py`:

```python
from fastapi.testclient import TestClient

from app.errores import ErrorDominio
from app.main import crear_app


def _cliente_con_ruta_de_prueba() -> TestClient:
    app = crear_app()

    @app.get("/api/prueba/error")
    def _falla():
        raise ErrorDominio("ALGO_INVALIDO", "Algo no se puede", 409)

    @app.get("/api/prueba/numero")
    def _numero(n: int):
        return {"n": n}

    return TestClient(app)


def test_error_dominio_tiene_status_422_por_defecto():
    assert ErrorDominio("X", "y").status == 422


def test_error_dominio_se_responde_con_formato_unico():
    r = _cliente_con_ruta_de_prueba().get("/api/prueba/error")
    assert r.status_code == 409
    assert r.json() == {"codigo": "ALGO_INVALIDO", "mensaje": "Algo no se puede"}


def test_error_de_validacion_se_reescribe_al_formato_unico():
    r = _cliente_con_ruta_de_prueba().get("/api/prueba/numero", params={"n": "abc"})
    assert r.status_code == 422
    cuerpo = r.json()
    assert set(cuerpo) == {"codigo", "mensaje"}
    assert cuerpo["codigo"] == "VALIDACION"
    assert "n" in cuerpo["mensaje"]


def test_ruta_inexistente_responde_404_con_formato_unico():
    r = _cliente_con_ruta_de_prueba().get("/api/no-existe")
    assert r.status_code == 404
    assert r.json()["codigo"] == "NO_ENCONTRADO"
```

`backend/tests/test_sin_hora_del_sistema.py`:

```python
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
PROHIBIDO = re.compile(r"datetime\.now\(|datetime\.utcnow\(|date\.today\(|time\.time\(")


def test_nadie_fuera_del_reloj_consulta_la_hora_del_sistema():
    infractores = [
        f"{archivo.relative_to(APP)}:{n}"
        for archivo in APP.rglob("*.py")
        if archivo.name != "reloj.py" or archivo.parent != APP
        for n, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), start=1)
        if PROHIBIDO.search(linea)
    ]
    assert infractores == [], f"Usar el reloj inyectable (D27): {infractores}"
```

- [ ] **Paso 6: correr y ver que fallan**

Run: `.venv/bin/pytest -q`
Expected: FAIL por `ModuleNotFoundError: No module named 'app.config'` (y similares).

- [ ] **Paso 7: implementar**

`backend/app/config.py`:

```python
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalizar_url(url: str) -> str:
    """Las cadenas de Supabase vienen como postgresql://; SQLAlchemy necesita el driver."""
    for prefijo in ("postgresql://", "postgres://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://guardia:guardia@localhost:5433/guardia"
    test_database_url: str = "postgresql+psycopg://guardia:guardia@localhost:5433/guardia_test"
    app_timezone: str = "America/Argentina/Buenos_Aires"
    modo_demo: bool = False

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _con_driver(cls, valor: str) -> str:
        return _normalizar_url(valor)

    @property
    def zona(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`backend/app/reloj.py`:

```python
"""Reloj inyectable (D27). Es el único módulo que consulta la hora del sistema."""

from datetime import datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from app.config import get_settings


class Reloj(Protocol):
    def ahora(self) -> datetime: ...


class RelojSistema:
    def __init__(self, zona: ZoneInfo) -> None:
        self._zona = zona

    def ahora(self) -> datetime:
        return datetime.now(self._zona)


class RelojFijo:
    """Reloj para pruebas: siempre devuelve el mismo instante hasta que se lo avanza."""

    def __init__(self, instante: datetime) -> None:
        if instante.tzinfo is None:
            raise ValueError("RelojFijo necesita un instante con zona horaria")
        self._instante = instante

    def ahora(self) -> datetime:
        return self._instante

    def avanzar(self, delta: timedelta) -> None:
        self._instante = self._instante + delta


def get_reloj() -> Reloj:
    return RelojSistema(get_settings().zona)
```

`backend/app/errores.py`:

```python
class ErrorDominio(Exception):
    """Error con código legible por la interfaz. Se responde como {"codigo", "mensaje"}."""

    def __init__(self, codigo: str, mensaje: str, status: int = 422) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.status = status
```

`backend/app/api/manejadores.py`:

```python
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
```

`backend/app/main.py`:

```python
from fastapi import APIRouter, FastAPI

from app.api.manejadores import registrar_manejadores


def crear_app() -> FastAPI:
    app = FastAPI(title="Guardia Viva", version="0.1.0")
    registrar_manejadores(app)

    api = APIRouter(prefix="/api")
    app.include_router(api)
    return app


app = crear_app()
```

- [ ] **Paso 8: correr y ver que pasan**

Run: `.venv/bin/pytest -q`
Expected: todas PASS.

- [ ] **Paso 9: commit**

```bash
git add .gitignore backend/pyproject.toml backend/.env.example backend/app backend/tests
git commit -m "Esqueleto del backend: configuración, reloj inyectable y formato de errores

Reloj inyectable según D27; formato único de errores {codigo, mensaje}.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarea 2: base de datos, Alembic, infraestructura de pruebas y GET /api/health

**Archivos:**
- Crear: `docker-compose.yml`, `backend/app/db.py`, `backend/app/modelos/__init__.py`, `backend/app/modelos/base.py`, `backend/app/api/health.py`, `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/script.py.mako`, `backend/migrations/versions/.gitkeep`, `backend/tests/conftest.py`
- Modificar: `backend/app/main.py`
- Pruebas: `backend/tests/test_health.py`, `backend/tests/test_infra_pruebas.py`

**Interfaces:**
- Consume: `get_settings`, `get_reloj`, `RelojFijo`, `ErrorDominio`, `crear_app` (tarea 1).
- Produce:
  - `app.db.engine`, `app.db.SessionLocal` y `app.db.get_db() -> Iterator[Session]`.
  - `app.modelos.Base` (`DeclarativeBase`).
  - Fixtures de pytest:
    - `engine`: sesión de pytest; recrea la base de prueba y aplica migraciones.
    - `sesion`: `Session` dentro de una transacción que se deshace; `commit()` solo confirma un savepoint.
    - `fabrica_sesiones`: `sessionmaker` real, solo en pruebas `@pytest.mark.commit_real`; vacía las tablas al terminar.
    - `cliente`: `TestClient` con `get_db` reemplazado según el marcador.
    - `reloj`: `RelojFijo` del 12/10/2026 09:00 en Buenos Aires, inyectado en la app.
  - En `conftest.py`: `verificar_base_local(url: str) -> None`.
  - `ZONA` en `conftest.py`.

- [ ] **Paso 1: crear `docker-compose.yml` en la raíz y levantar Postgres**

```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: guardia
      POSTGRES_PASSWORD: guardia
      POSTGRES_DB: guardia
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U guardia"]
      interval: 2s
      timeout: 3s
      retries: 15
```

Run (desde la raíz): `docker compose up -d --wait`
Expected: el contenedor queda `healthy`.

- [ ] **Paso 2: crear la base declarativa y la sesión**

`backend/app/modelos/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

`backend/app/modelos/__init__.py`:

```python
from app.modelos.base import Base

__all__ = ["Base"]
```

`backend/app/db.py`:

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as sesion:
        yield sesion
```

- [ ] **Paso 3: configurar Alembic**

`backend/alembic.ini`:

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
# La URL sale de app.config (DATABASE_URL); las pruebas la fijan con set_main_option.
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %%(levelname)-5.5s [%%(name)s] %%(message)s
```

`backend/migrations/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_settings
from app.modelos import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as conexion:
        context.configure(connection=conexion, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

`backend/migrations/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Crear vacío `backend/migrations/versions/.gitkeep`.

Run: `.venv/bin/alembic upgrade head`
Expected: termina sin errores (todavía no hay migraciones).

- [ ] **Paso 4: crear `backend/tests/conftest.py`**

```python
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db import get_db
from app.main import app
from app.reloj import RelojFijo, get_reloj

BACKEND = Path(__file__).resolve().parents[1]
ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
HOSTS_LOCALES = {"localhost", "127.0.0.1", "postgres"}


def verificar_base_local(url: str) -> None:
    """La infraestructura de pruebas borra y recrea la base: nunca contra una base remota."""
    host = make_url(url).host
    if host not in HOSTS_LOCALES:
        raise RuntimeError(
            f"TEST_DATABASE_URL apunta a '{host}'. Las pruebas solo corren contra el Postgres local de docker-compose."
        )


def _recrear_base(url: str) -> None:
    destino = make_url(url)
    admin = create_engine(destino.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conexion:
        conexion.execute(text(f'DROP DATABASE IF EXISTS "{destino.database}" WITH (FORCE)'))
        conexion.execute(text(f'CREATE DATABASE "{destino.database}"'))
    admin.dispose()


def _vaciar_tablas(engine: Engine) -> None:
    with engine.begin() as conexion:
        tablas = conexion.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'")
        ).scalars().all()
        if tablas:
            lista = ", ".join(f'"{t}"' for t in tablas)
            conexion.execute(text(f"TRUNCATE {lista} RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = get_settings().test_database_url
    verificar_base_local(url)
    _recrear_base(url)
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    motor = create_engine(url)
    yield motor
    motor.dispose()


@pytest.fixture
def sesion(engine: Engine) -> Iterator[Session]:
    """Sesión dentro de una transacción que se deshace al terminar la prueba."""
    conexion = engine.connect()
    transaccion = conexion.begin()
    s = Session(bind=conexion, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield s
    s.close()
    transaccion.rollback()
    conexion.close()


@pytest.fixture
def fabrica_sesiones(engine: Engine, request: pytest.FixtureRequest) -> Iterator[sessionmaker[Session]]:
    """Sesiones que confirman de verdad. Solo para pruebas @pytest.mark.commit_real (concurrencia, F3)."""
    if request.node.get_closest_marker("commit_real") is None:
        raise RuntimeError("fabrica_sesiones solo se usa en pruebas marcadas con @pytest.mark.commit_real")
    yield sessionmaker(bind=engine, expire_on_commit=False)
    _vaciar_tablas(engine)


@pytest.fixture
def cliente(request: pytest.FixtureRequest) -> Iterator[TestClient]:
    if request.node.get_closest_marker("commit_real") is not None:
        fabrica = request.getfixturevalue("fabrica_sesiones")

        def _get_db() -> Iterator[Session]:
            with fabrica() as s:
                yield s
    else:
        compartida = request.getfixturevalue("sesion")

        def _get_db() -> Iterator[Session]:
            yield compartida

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def reloj() -> Iterator[RelojFijo]:
    fijo = RelojFijo(datetime(2026, 10, 12, 9, 0, tzinfo=ZONA))
    app.dependency_overrides[get_reloj] = lambda: fijo
    yield fijo
    app.dependency_overrides.pop(get_reloj, None)
```

- [ ] **Paso 5: escribir las pruebas que fallan**

`backend/tests/test_infra_pruebas.py`:

```python
import pytest
from sqlalchemy import text

from conftest import verificar_base_local


def test_verificar_base_local_acepta_localhost():
    verificar_base_local("postgresql+psycopg://guardia:guardia@localhost:5433/guardia_test")


def test_verificar_base_local_rechaza_host_remoto():
    with pytest.raises(RuntimeError, match="pooler.supabase.com"):
        verificar_base_local("postgresql+psycopg://u:p@aws-0-sa-east-1.pooler.supabase.com:5432/postgres")


def test_sesion_apunta_a_la_base_de_prueba(sesion):
    assert sesion.execute(text("SELECT current_database()")).scalar_one() == "guardia_test"


def test_fabrica_sesiones_fuera_de_commit_real_falla(request):
    with pytest.raises(RuntimeError, match="commit_real"):
        request.getfixturevalue("fabrica_sesiones")
```

`backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.main import app


def test_health_responde_ok_con_la_hora_del_reloj(cliente, reloj):
    r = cliente.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok", "base": "ok", "ahora": "2026-10-12T09:00:00-03:00"}


class _SesionCaida:
    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("conexión rechazada"))


def test_health_sin_base_responde_503():
    app.dependency_overrides[get_db] = lambda: _SesionCaida()
    try:
        with TestClient(app) as c:
            r = c.get("/api/health")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 503
    assert r.json()["codigo"] == "BASE_NO_DISPONIBLE"
```

- [ ] **Paso 6: correr y ver que fallan**

Run: `.venv/bin/pytest tests/test_health.py tests/test_infra_pruebas.py -v`
Expected: las pruebas de health fallan con 404 (`NO_ENCONTRADO`). Las de infraestructura ya pasan.

- [ ] **Paso 7: implementar el endpoint y registrarlo**

`backend/app/api/health.py`:

```python
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
```

`backend/app/main.py` (reemplazo completo):

```python
from fastapi import APIRouter, FastAPI

from app.api import health
from app.api.manejadores import registrar_manejadores


def crear_app() -> FastAPI:
    app = FastAPI(title="Guardia Viva", version="0.1.0")
    registrar_manejadores(app)

    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    app.include_router(api)
    return app


app = crear_app()
```

- [ ] **Paso 8: correr toda la suite**

Run: `.venv/bin/pytest -q`
Expected: todas PASS.

- [ ] **Paso 9: commit**

```bash
git add docker-compose.yml backend/alembic.ini backend/migrations backend/app backend/tests
git commit -m "Conexión a Postgres, Alembic, infraestructura de pruebas y GET /api/health

Pruebas contra Postgres 15 en docker-compose, con transacción que se deshace
y marcador commit_real para las pruebas de concurrencia de F3.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarea 3: cálculo de turnos (dominio puro)

**Archivos:**
- Crear: `backend/app/dominio/__init__.py` (vacío), `backend/app/dominio/calendario.py`
- Pruebas: `backend/tests/test_calendario.py`

**Interfaces:**
- Consume: `app.errores.ErrorDominio`.
- Produce (todas en `app.dominio.calendario`):
  - `Titular(id: int, nombre: str)`, dataclass inmutable.
  - `VersionPlantilla`, dataclass inmutable con `version_id: int`, `horario_id: int`, `titular: Titular | None`, `dia_semana: int`, `hora_inicio: time`, `duracion_horas: int`, `frecuencia_semanas: int`, `fecha_ancla: date`, `vigente_desde: date`, `vigente_hasta: date | None`.
  - `TurnoCalculado`, dataclass inmutable con `id: str`, `horario_id: int`, `fecha: date`, `inicio: datetime`, `fin: datetime`, `duracion_horas: int`, `version_id: int`, `titular: Titular | None`.
  - `calcular_turnos(versiones: Sequence[VersionPlantilla], desde: date, hasta: date, zona: ZoneInfo) -> list[TurnoCalculado]`.
  - `formatear_id_turno(horario_id: int, fecha: date) -> str`.
  - `parsear_id_turno(texto: str) -> tuple[int, date]`.

Fechas de referencia: el lunes 7/9/2026, el lunes 28/9/2026, el lunes 5/10/2026 y el lunes 12/10/2026. El sábado 17/10/2026.

- [ ] **Paso 1: escribir las pruebas que fallan**

`backend/tests/test_calendario.py`:

```python
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.dominio.calendario import (
    Titular,
    VersionPlantilla,
    calcular_turnos,
    formatear_id_turno,
    parsear_id_turno,
)
from app.errores import ErrorDominio

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
FLORENCIA = Titular(1, "Florencia Lucca")
MARIANO = Titular(2, "Mariano Reimondez")


def version(
    horario_id=1,
    version_id=None,
    dia=1,
    hora=time(8),
    dur=12,
    frec=1,
    ancla=date(2026, 9, 7),
    desde=date(2026, 9, 7),
    hasta=None,
    titular=FLORENCIA,
):
    return VersionPlantilla(
        version_id=version_id if version_id is not None else horario_id,
        horario_id=horario_id,
        titular=titular,
        dia_semana=dia,
        hora_inicio=hora,
        duracion_horas=dur,
        frecuencia_semanas=frec,
        fecha_ancla=ancla,
        vigente_desde=desde,
        vigente_hasta=hasta,
    )


def turnos(versiones, desde, hasta):
    return calcular_turnos(versiones, desde, hasta, ZONA)


def fechas(lista):
    return [t.fecha for t in lista]


def en_ba(*args):
    return datetime(*args, tzinfo=ZONA)


# Semanal

def test_horario_semanal_genera_un_turno_en_el_dia_correcto():
    [t] = turnos([version(dia=3)], date(2026, 10, 12), date(2026, 10, 18))
    assert t.id == "1:2026-10-14"
    assert t.fecha == date(2026, 10, 14)
    assert t.inicio == en_ba(2026, 10, 14, 8, 0)
    assert t.fin == en_ba(2026, 10, 14, 20, 0)
    assert t.duracion_horas == 12
    assert t.titular == FLORENCIA
    assert t.version_id == 1


def test_horario_semanal_genera_un_turno_por_semana():
    resultado = turnos([version(dia=3)], date(2026, 10, 12), date(2026, 11, 1))
    assert fechas(resultado) == [date(2026, 10, 14), date(2026, 10, 21), date(2026, 10, 28)]


# Semana por medio (D14)

def test_semana_por_medio_salta_las_semanas_que_no_cumplen_la_frecuencia():
    v = version(dia=4, frec=2, ancla=date(2026, 10, 12))
    resultado = turnos([v], date(2026, 10, 5), date(2026, 11, 8))
    assert fechas(resultado) == [date(2026, 10, 15), date(2026, 10, 29)]


def test_semana_por_medio_funciona_antes_de_la_fecha_ancla():
    v = version(dia=4, frec=2, ancla=date(2026, 10, 12))
    resultado = turnos([v], date(2026, 9, 21), date(2026, 10, 4))
    assert fechas(resultado) == [date(2026, 10, 1)]


def test_dos_horarios_quincenales_desfasados_alternan_el_mismo_hueco():
    martin = version(horario_id=5, dia=4, dur=24, frec=2, ancla=date(2026, 10, 12), titular=MARIANO)
    javier = version(horario_id=6, dia=4, dur=24, frec=2, ancla=date(2026, 10, 5))
    resultado = turnos([martin, javier], date(2026, 10, 5), date(2026, 10, 25))
    assert [(t.horario_id, t.fecha) for t in resultado if t.fecha.isoweekday() == 4] == [
        (6, date(2026, 10, 8)),
        (5, date(2026, 10, 15)),
        (6, date(2026, 10, 22)),
    ]


# Medianoche

def test_turno_que_cruza_la_medianoche_aparece_en_los_dos_dias():
    v = version(dia=1, hora=time(22), dur=8)
    [lunes] = turnos([v], date(2026, 10, 12), date(2026, 10, 12))
    [martes] = turnos([v], date(2026, 10, 13), date(2026, 10, 13))
    assert lunes.id == martes.id == "1:2026-10-12"
    assert lunes.fin == en_ba(2026, 10, 13, 6, 0)
    assert turnos([v], date(2026, 10, 14), date(2026, 10, 14)) == []


def test_turno_de_24_horas_aparece_en_los_dos_dias_que_toca():
    v = version(dia=1, hora=time(8), dur=24)
    assert fechas(turnos([v], date(2026, 10, 13), date(2026, 10, 13))) == [date(2026, 10, 12)]
    assert turnos([v], date(2026, 10, 12), date(2026, 10, 12))[0].fin == en_ba(2026, 10, 13, 8, 0)


def test_turno_que_termina_justo_a_las_00_de_desde_no_aparece():
    domingo = version(dia=7, hora=time(16), dur=8)
    assert turnos([domingo], date(2026, 10, 12), date(2026, 10, 12)) == []
    assert fechas(turnos([domingo], date(2026, 10, 11), date(2026, 10, 11))) == [date(2026, 10, 11)]


def test_turno_de_24_horas_desde_las_00_no_aparece_al_dia_siguiente():
    v = version(dia=1, hora=time(0), dur=24)
    assert turnos([v], date(2026, 10, 13), date(2026, 10, 13)) == []


# Superposición entre médicos

def test_horarios_superpuestos_de_distintos_medicos_generan_dos_turnos():
    a = version(horario_id=9, dia=3, hora=time(8), dur=12, titular=FLORENCIA)
    b = version(horario_id=10, dia=3, hora=time(14), dur=6, titular=MARIANO)
    resultado = turnos([b, a], date(2026, 10, 14), date(2026, 10, 14))
    assert [(t.horario_id, t.titular) for t in resultado] == [(9, FLORENCIA), (10, MARIANO)]


def test_mismo_inicio_se_ordena_por_horario():
    a = version(horario_id=3, dia=3)
    b = version(horario_id=2, dia=3, titular=MARIANO)
    resultado = turnos([a, b], date(2026, 10, 14), date(2026, 10, 14))
    assert [t.horario_id for t in resultado] == [2, 3]


# Cambio de versión

def test_cambio_de_version_usa_la_vieja_antes_y_la_nueva_despues():
    vieja = version(horario_id=7, version_id=1, dia=2, hora=time(7), hasta=date(2026, 9, 28))
    nueva = version(horario_id=7, version_id=2, dia=2, hora=time(8), desde=date(2026, 9, 28))
    resultado = turnos([vieja, nueva], date(2026, 9, 21), date(2026, 10, 4))
    assert [(t.id, t.inicio, t.version_id) for t in resultado] == [
        ("7:2026-09-22", en_ba(2026, 9, 22, 7, 0), 1),
        ("7:2026-09-29", en_ba(2026, 9, 29, 8, 0), 2),
    ]


def test_cambio_de_version_puede_cambiar_el_dia():
    vieja = version(horario_id=7, version_id=1, dia=2, hasta=date(2026, 9, 28))
    nueva = version(horario_id=7, version_id=2, dia=4, desde=date(2026, 9, 28))
    resultado = turnos([vieja, nueva], date(2026, 9, 21), date(2026, 10, 4))
    assert [t.id for t in resultado] == ["7:2026-09-22", "7:2026-10-01"]


def test_turno_del_ultimo_dia_de_vigencia_pertenece_a_la_version_vieja():
    vieja = version(horario_id=4, version_id=1, dia=7, hora=time(20), hasta=date(2026, 10, 12))
    nueva = version(horario_id=4, version_id=2, dia=7, hora=time(8), desde=date(2026, 10, 12))
    [t] = turnos([vieja, nueva], date(2026, 10, 12), date(2026, 10, 12))
    assert t.version_id == 1
    assert t.fecha == date(2026, 10, 11)
    assert t.fin == en_ba(2026, 10, 12, 8, 0)


def test_no_hay_turnos_antes_de_la_vigencia():
    v = version(dia=3, desde=date(2026, 10, 14))
    assert fechas(turnos([v], date(2026, 10, 5), date(2026, 10, 18))) == [date(2026, 10, 14)]


# Sin titular (D24)

def test_version_sin_titular_genera_turno_con_titular_none():
    [t] = turnos([version(dia=3, titular=None)], date(2026, 10, 14), date(2026, 10, 14))
    assert t.titular is None


# Identificador (D09)

def test_formatear_y_parsear_id_son_inversas():
    texto = formatear_id_turno(7, date(2026, 10, 17))
    assert texto == "7:2026-10-17"
    assert parsear_id_turno(texto) == (7, date(2026, 10, 17))


@pytest.mark.parametrize("texto", ["abc", "7-2026-10-10", "7:2026-13-01", "7:2026-10-1", ":2026-10-10", "x:2026-10-10"])
def test_parsear_id_invalido_lanza_turno_id_invalido(texto):
    with pytest.raises(ErrorDominio) as error:
        parsear_id_turno(texto)
    assert error.value.codigo == "TURNO_ID_INVALIDO"
    assert error.value.status == 422
```

- [ ] **Paso 2: correr y ver que fallan**

Run: `.venv/bin/pytest tests/test_calendario.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.dominio'`.

- [ ] **Paso 3: implementar `backend/app/dominio/calendario.py`**

Crear vacío `backend/app/dominio/__init__.py`.

```python
"""Cálculo de turnos desde la plantilla (D11, D13, D14). Lógica pura: sin base de datos ni FastAPI."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.errores import ErrorDominio


@dataclass(frozen=True)
class Titular:
    id: int
    nombre: str


@dataclass(frozen=True)
class VersionPlantilla:
    version_id: int
    horario_id: int
    titular: Titular | None
    dia_semana: int
    hora_inicio: time
    duracion_horas: int
    frecuencia_semanas: int
    fecha_ancla: date
    vigente_desde: date
    vigente_hasta: date | None


@dataclass(frozen=True)
class TurnoCalculado:
    id: str
    horario_id: int
    fecha: date
    inicio: datetime
    fin: datetime
    duracion_horas: int
    version_id: int
    titular: Titular | None


def formatear_id_turno(horario_id: int, fecha: date) -> str:
    return f"{horario_id}:{fecha.isoformat()}"


_PATRON_ID = re.compile(r"^(\d+):(\d{4}-\d{2}-\d{2})$")


def parsear_id_turno(texto: str) -> tuple[int, date]:
    coincidencia = _PATRON_ID.match(texto)
    if coincidencia is None:
        raise ErrorDominio("TURNO_ID_INVALIDO", f"Identificador de turno inválido: {texto!r}.")
    try:
        fecha = date.fromisoformat(coincidencia.group(2))
    except ValueError as exc:
        raise ErrorDominio("TURNO_ID_INVALIDO", f"Identificador de turno inválido: {texto!r}.") from exc
    return int(coincidencia.group(1)), fecha


def _lunes(fecha: date) -> date:
    return fecha - timedelta(days=fecha.weekday())


def _se_cumple(version: VersionPlantilla, fecha: date) -> bool:
    if fecha.isoweekday() != version.dia_semana:
        return False
    # La vigencia se evalúa sobre la fecha de inicio: el turno pertenece al día en que empieza (D13).
    if fecha < version.vigente_desde:
        return False
    if version.vigente_hasta is not None and fecha >= version.vigente_hasta:
        return False
    semanas = (_lunes(fecha) - version.fecha_ancla).days // 7
    return semanas % version.frecuencia_semanas == 0


def calcular_turnos(
    versiones: Sequence[VersionPlantilla], desde: date, hasta: date, zona: ZoneInfo
) -> list[TurnoCalculado]:
    """Turnos cuyo intervalo se superpone con [desde 00:00, hasta + 1 día 00:00) en la zona del servicio."""
    inicio_ventana = datetime.combine(desde, time(0), tzinfo=zona)
    fin_ventana = datetime.combine(hasta + timedelta(days=1), time(0), tzinfo=zona)

    resultado: list[TurnoCalculado] = []
    # Con duración máxima de 24 h, solo un turno del día anterior puede entrar en la ventana.
    fecha = desde - timedelta(days=1)
    while fecha <= hasta:
        for version in versiones:
            if not _se_cumple(version, fecha):
                continue
            inicio = datetime.combine(fecha, version.hora_inicio, tzinfo=zona)
            fin = (inicio.astimezone(UTC) + timedelta(hours=version.duracion_horas)).astimezone(zona)
            if inicio < fin_ventana and fin > inicio_ventana:
                resultado.append(
                    TurnoCalculado(
                        id=formatear_id_turno(version.horario_id, fecha),
                        horario_id=version.horario_id,
                        fecha=fecha,
                        inicio=inicio,
                        fin=fin,
                        duracion_horas=version.duracion_horas,
                        version_id=version.version_id,
                        titular=version.titular,
                    )
                )
        fecha += timedelta(days=1)

    resultado.sort(key=lambda turno: (turno.inicio, turno.horario_id))
    return resultado
```

- [ ] **Paso 4: correr y ver que pasan**

Run: `.venv/bin/pytest tests/test_calendario.py -q`
Expected: todas PASS.

- [ ] **Paso 5: commit**

```bash
git add backend/app/dominio backend/tests/test_calendario.py
git commit -m "Cálculo de turnos desde la plantilla (D13, D14) e identificador de turno (D09)

Función pura: frecuencia con fecha ancla, turnos que cruzan medianoche,
vigencia evaluada sobre la fecha de inicio.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarea 4: modelo de datos y migración (Usuario, HorarioPactado, VersionHorario)

**Archivos:**
- Crear: `backend/app/modelos/usuario.py`, `backend/app/modelos/horario.py`, `backend/migrations/versions/0001_usuarios_y_plantilla.py`, `backend/tests/fabricas.py`
- Modificar: `backend/app/modelos/__init__.py`
- Pruebas: `backend/tests/test_modelo.py`

**Interfaces:**
- Consume: `Base` y las fixtures `sesion`, `engine` y `fabrica_sesiones` (tarea 2).
- Produce:
  - `app.modelos.RolUsuario` (MEDICO, COORDINADOR) y `app.modelos.EstadoUsuario` (PENDIENTE, ACTIVO, BAJA), `str` + `Enum`.
  - `app.modelos.Usuario`: `id`, `nombre`, `email`, `rol`, `estado`, `fecha_baja`, `auth_id`, `creado_en`.
  - `app.modelos.HorarioPactado`: `id`, `creado_en`, `versiones`.
  - `app.modelos.VersionHorario`: `id`, `horario_id`, `medico_id`, `medico`, `dia_semana`, `hora_inicio`, `duracion_horas`, `frecuencia_semanas`, `fecha_ancla`, `vigente_desde`, `vigente_hasta`, `vigencia` (generada).
  - `tests.fabricas.crear_usuario(sesion, nombre, rol=RolUsuario.MEDICO, estado=EstadoUsuario.ACTIVO, email=None) -> Usuario`.

- [ ] **Paso 1: escribir la migración**

`backend/migrations/versions/0001_usuarios_y_plantilla.py`:

```python
"""Usuarios y plantilla de horarios pactados (D08, D10, D23, D24, D07)

Revision ID: 0001
Revises:
Create Date: 2026-10-05
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_UPGRADE = [
    "CREATE EXTENSION IF NOT EXISTS btree_gist",
    "CREATE TYPE rol_usuario AS ENUM ('MEDICO', 'COORDINADOR')",
    "CREATE TYPE estado_usuario AS ENUM ('PENDIENTE', 'ACTIVO', 'BAJA')",
    """
    CREATE TABLE usuario (
        id serial PRIMARY KEY,
        nombre text NOT NULL,
        email text NOT NULL,
        rol rol_usuario NOT NULL,
        estado estado_usuario NOT NULL DEFAULT 'PENDIENTE',
        fecha_baja date,
        auth_id uuid UNIQUE,
        creado_en timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE UNIQUE INDEX ux_usuario_email_lower ON usuario (lower(email))",
    """
    CREATE TABLE horario_pactado (
        id serial PRIMARY KEY,
        creado_en timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE version_horario (
        id serial PRIMARY KEY,
        horario_id integer NOT NULL REFERENCES horario_pactado (id),
        medico_id integer REFERENCES usuario (id),
        dia_semana smallint NOT NULL,
        hora_inicio time NOT NULL,
        duracion_horas smallint NOT NULL,
        frecuencia_semanas smallint NOT NULL,
        fecha_ancla date NOT NULL,
        vigente_desde date NOT NULL,
        vigente_hasta date,
        vigencia daterange GENERATED ALWAYS AS (daterange(vigente_desde, vigente_hasta, '[)')) STORED,
        CONSTRAINT ck_version_horario_dia_semana CHECK (dia_semana BETWEEN 1 AND 7),
        CONSTRAINT ck_version_horario_duracion CHECK (duracion_horas BETWEEN 1 AND 24),
        CONSTRAINT ck_version_horario_frecuencia CHECK (frecuencia_semanas >= 1),
        CONSTRAINT ck_version_horario_ancla_lunes CHECK (extract(isodow FROM fecha_ancla) = 1),
        CONSTRAINT ck_version_horario_vigencia CHECK (vigente_hasta IS NULL OR vigente_hasta > vigente_desde),
        CONSTRAINT ex_version_horario_vigencia EXCLUDE USING gist (horario_id WITH =, vigencia WITH &&)
    )
    """,
    "CREATE INDEX ix_version_horario_medico ON version_horario (medico_id)",
    # D07: RLS activado sin políticas; el backend se conecta como dueño de las tablas.
    "ALTER TABLE usuario ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE horario_pactado ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE version_horario ENABLE ROW LEVEL SECURITY",
]

_DOWNGRADE = [
    "DROP TABLE version_horario",
    "DROP TABLE horario_pactado",
    "DROP TABLE usuario",
    "DROP TYPE estado_usuario",
    "DROP TYPE rol_usuario",
]


def upgrade() -> None:
    for sentencia in _UPGRADE:
        op.execute(sentencia)


def downgrade() -> None:
    for sentencia in _DOWNGRADE:
        op.execute(sentencia)
```

- [ ] **Paso 2: escribir los modelos**

`backend/app/modelos/usuario.py`:

```python
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import DateTime, Enum, Index, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class RolUsuario(str, enum.Enum):
    MEDICO = "MEDICO"
    COORDINADOR = "COORDINADOR"


class EstadoUsuario(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    ACTIVO = "ACTIVO"
    BAJA = "BAJA"


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    rol: Mapped[RolUsuario] = mapped_column(Enum(RolUsuario, name="rol_usuario"))
    estado: Mapped[EstadoUsuario] = mapped_column(
        Enum(EstadoUsuario, name="estado_usuario"), server_default=EstadoUsuario.PENDIENTE.value
    )
    fecha_baja: Mapped[date | None]
    auth_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index("ux_usuario_email_lower", func.lower(Usuario.email), unique=True)
```

`backend/app/modelos/horario.py`:

```python
from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, SmallInteger, func
from sqlalchemy.dialects.postgresql import DATERANGE, ExcludeConstraint, Range
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modelos.base import Base
from app.modelos.usuario import Usuario


class HorarioPactado(Base):
    """Identidad estable de un horario semanal (D09, D10). Los datos viven en sus versiones."""

    __tablename__ = "horario_pactado"

    id: Mapped[int] = mapped_column(primary_key=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    versiones: Mapped[list["VersionHorario"]] = relationship(
        back_populates="horario", order_by="VersionHorario.vigente_desde"
    )


class VersionHorario(Base):
    """Versión de un horario pactado con vigencia [vigente_desde, vigente_hasta) (D10, D14, D24)."""

    __tablename__ = "version_horario"
    __table_args__ = (
        CheckConstraint("dia_semana BETWEEN 1 AND 7", name="ck_version_horario_dia_semana"),
        CheckConstraint("duracion_horas BETWEEN 1 AND 24", name="ck_version_horario_duracion"),
        CheckConstraint("frecuencia_semanas >= 1", name="ck_version_horario_frecuencia"),
        CheckConstraint("extract(isodow FROM fecha_ancla) = 1", name="ck_version_horario_ancla_lunes"),
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="ck_version_horario_vigencia"
        ),
        ExcludeConstraint(
            ("horario_id", "="), ("vigencia", "&&"), name="ex_version_horario_vigencia", using="gist"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    horario_id: Mapped[int] = mapped_column(ForeignKey("horario_pactado.id"))
    medico_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    dia_semana: Mapped[int] = mapped_column(SmallInteger)
    hora_inicio: Mapped[time]
    duracion_horas: Mapped[int] = mapped_column(SmallInteger)
    frecuencia_semanas: Mapped[int] = mapped_column(SmallInteger)
    fecha_ancla: Mapped[date]
    vigente_desde: Mapped[date]
    vigente_hasta: Mapped[date | None]
    vigencia: Mapped[Range[date]] = mapped_column(
        DATERANGE, Computed("daterange(vigente_desde, vigente_hasta, '[)')", persisted=True)
    )

    horario: Mapped[HorarioPactado] = relationship(back_populates="versiones")
    medico: Mapped[Usuario | None] = relationship()
```

`backend/app/modelos/__init__.py` (reemplazo completo):

```python
from app.modelos.base import Base
from app.modelos.horario import HorarioPactado, VersionHorario
from app.modelos.usuario import EstadoUsuario, RolUsuario, Usuario

__all__ = ["Base", "EstadoUsuario", "HorarioPactado", "RolUsuario", "Usuario", "VersionHorario"]
```

`backend/tests/fabricas.py`:

```python
from itertools import count

from sqlalchemy.orm import Session

from app.modelos import EstadoUsuario, RolUsuario, Usuario

_secuencia = count(1)


def crear_usuario(
    sesion: Session,
    nombre: str,
    rol: RolUsuario = RolUsuario.MEDICO,
    estado: EstadoUsuario = EstadoUsuario.ACTIVO,
    email: str | None = None,
) -> Usuario:
    usuario = Usuario(
        nombre=nombre,
        email=email or f"usuario{next(_secuencia)}@prueba.test",
        rol=rol,
        estado=estado,
    )
    sesion.add(usuario)
    sesion.flush()
    return usuario
```

- [ ] **Paso 3: escribir las pruebas**

`backend/tests/test_modelo.py`:

```python
from datetime import date, time

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.modelos import EstadoUsuario, HorarioPactado, RolUsuario, Usuario, VersionHorario
from fabricas import crear_usuario


def nuevo_horario(sesion) -> HorarioPactado:
    horario = HorarioPactado()
    sesion.add(horario)
    sesion.flush()
    return horario


def fila_version(horario, **cambios) -> VersionHorario:
    datos = dict(
        horario_id=horario.id,
        medico_id=None,
        dia_semana=1,
        hora_inicio=time(8),
        duracion_horas=12,
        frecuencia_semanas=1,
        fecha_ancla=date(2026, 9, 7),
        vigente_desde=date(2026, 9, 7),
        vigente_hasta=None,
    )
    datos.update(cambios)
    return VersionHorario(**datos)


def guardar(sesion, objeto):
    sesion.add(objeto)
    sesion.flush()


def debe_fallar(sesion, objeto):
    with pytest.raises(IntegrityError):
        with sesion.begin_nested():
            guardar(sesion, objeto)


def test_migracion_crea_las_tablas_con_rls(sesion):
    filas = sesion.execute(
        text(
            "SELECT relname, relrowsecurity FROM pg_class "
            "WHERE relname IN ('usuario', 'horario_pactado', 'version_horario') ORDER BY relname"
        )
    ).all()
    assert filas == [("horario_pactado", True), ("usuario", True), ("version_horario", True)]


def test_usuario_estado_por_defecto_es_pendiente(sesion):
    usuario = Usuario(nombre="Nuevo", email="nuevo@prueba.test", rol=RolUsuario.MEDICO)
    guardar(sesion, usuario)
    sesion.refresh(usuario)
    assert usuario.estado == EstadoUsuario.PENDIENTE


def test_email_unico_sin_distinguir_mayusculas(sesion):
    crear_usuario(sesion, "Florencia", email="Florencia@Prueba.test")
    debe_fallar(sesion, Usuario(nombre="Otra", email="florencia@prueba.TEST", rol=RolUsuario.MEDICO))


def test_exclusion_rechaza_vigencias_superpuestas_del_mismo_horario(sesion):
    horario = nuevo_horario(sesion)
    guardar(sesion, fila_version(horario, vigente_hasta=date(2026, 10, 12)))
    debe_fallar(sesion, fila_version(horario, vigente_desde=date(2026, 10, 5)))


def test_exclusion_rechaza_dos_versiones_abiertas_del_mismo_horario(sesion):
    horario = nuevo_horario(sesion)
    guardar(sesion, fila_version(horario))
    debe_fallar(sesion, fila_version(horario, vigente_desde=date(2026, 12, 7)))


def test_exclusion_acepta_vigencias_contiguas(sesion):
    horario = nuevo_horario(sesion)
    guardar(sesion, fila_version(horario, vigente_hasta=date(2026, 9, 28)))
    guardar(sesion, fila_version(horario, vigente_desde=date(2026, 9, 28)))
    cantidad = sesion.scalar(select(func.count()).where(VersionHorario.horario_id == horario.id))
    assert cantidad == 2


def test_horarios_distintos_pueden_superponerse(sesion):
    guardar(sesion, fila_version(nuevo_horario(sesion)))
    guardar(sesion, fila_version(nuevo_horario(sesion)))


def test_vigencia_generada_es_semiabierta(sesion):
    horario = nuevo_horario(sesion)
    version = fila_version(horario, vigente_hasta=date(2026, 9, 28))
    guardar(sesion, version)
    contiene = sesion.execute(
        text("SELECT vigencia @> date '2026-09-27', vigencia @> date '2026-09-28' FROM version_horario WHERE id = :id"),
        {"id": version.id},
    ).one()
    assert tuple(contiene) == (True, False)


@pytest.mark.parametrize(
    "cambios",
    [
        {"fecha_ancla": date(2026, 9, 8)},
        {"duracion_horas": 0},
        {"duracion_horas": 25},
        {"dia_semana": 0},
        {"dia_semana": 8},
        {"frecuencia_semanas": 0},
        {"vigente_hasta": date(2026, 9, 7)},
        {"vigente_hasta": date(2026, 9, 1)},
    ],
)
def test_checks_rechazan_valores_invalidos(sesion, cambios):
    debe_fallar(sesion, fila_version(nuevo_horario(sesion), **cambios))


def test_version_acepta_medico_vacio_y_medico_asignado(sesion):
    medico = crear_usuario(sesion, "Mariano")
    horario = nuevo_horario(sesion)
    guardar(sesion, fila_version(horario, medico_id=medico.id, vigente_hasta=date(2026, 10, 12)))
    guardar(sesion, fila_version(horario, medico_id=None, vigente_desde=date(2026, 10, 12)))
    assert [v.medico_id for v in sesion.scalars(select(VersionHorario).order_by(VersionHorario.vigente_desde))] == [
        medico.id,
        None,
    ]


@pytest.mark.commit_real
def test_commit_real_confirma_y_otra_sesion_lo_ve(fabrica_sesiones):
    with fabrica_sesiones() as primera:
        primera.add(Usuario(nombre="Confirmado", email="confirmado@prueba.test", rol=RolUsuario.MEDICO))
        primera.commit()
    with fabrica_sesiones() as segunda:
        assert segunda.scalar(select(func.count()).select_from(Usuario)) == 1


def test_despues_de_commit_real_la_base_queda_vacia(engine):
    # Corre después de la prueba anterior (orden del archivo): el fixture debe haber vaciado las tablas.
    with engine.connect() as conexion:
        assert conexion.execute(text("SELECT count(*) FROM usuario")).scalar_one() == 0
```

- [ ] **Paso 4: correr las pruebas**

Run: `.venv/bin/pytest -q`
Expected: todas PASS. Si `test_migracion_crea_las_tablas_con_rls` falla, revisar que el fixture `engine` haya recreado la base (la migración nueva se aplica al recrearla).

- [ ] **Paso 5: verificar que la migración baja y sube**

Run: `.venv/bin/alembic upgrade head && .venv/bin/alembic downgrade base && .venv/bin/alembic upgrade head` (contra la base local `guardia`, sin `.env` o con `DATABASE_URL` local)
Expected: los tres comandos terminan sin errores.

- [ ] **Paso 6: commit**

```bash
git add backend/app/modelos backend/migrations/versions/0001_usuarios_y_plantilla.py backend/tests/fabricas.py backend/tests/test_modelo.py
git commit -m "Tablas usuario, horario_pactado y version_horario (D10, D23, D24)

Exclusión de vigencias superpuestas con btree_gist, vigencia como daterange
generado, médico opcional en la versión y RLS sin políticas (D07).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarea 5: repositorio de horarios

**Archivos:**
- Crear: `backend/app/repos/__init__.py` (vacío), `backend/app/repos/horarios.py`
- Pruebas: `backend/tests/test_repo_horarios.py`

**Interfaces:**
- Consume: los modelos (tarea 4), `VersionPlantilla` y `Titular` (tarea 3), `crear_usuario` (tarea 4).
- Produce (en `app.repos.horarios`):
  - `DatosVersion`, dataclass inmutable con `medico_id: int | None`, `dia_semana: int`, `hora_inicio: time`, `duracion_horas: int`, `frecuencia_semanas: int`, `fecha_ancla: date`.
  - `crear_horario(sesion: Session, datos: DatosVersion, vigente_desde: date, vigente_hasta: date | None = None) -> HorarioPactado`.
  - `nueva_version(sesion: Session, horario_id: int, datos: DatosVersion, desde: date) -> VersionHorario`.
  - `versiones_en_rango(sesion: Session, desde: date, hasta: date) -> list[VersionPlantilla]`.

  Ninguna hace commit: trabajan dentro de la transacción de quien llama.

- [ ] **Paso 1: escribir las pruebas que fallan**

`backend/tests/test_repo_horarios.py`:

```python
from datetime import date, time

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dominio.calendario import Titular
from app.modelos import VersionHorario
from app.repos.horarios import DatosVersion, crear_horario, nueva_version, versiones_en_rango
from fabricas import crear_usuario


def datos(medico_id=None, dia=2, hora=time(7), dur=12, frec=1, ancla=date(2026, 9, 7)) -> DatosVersion:
    return DatosVersion(
        medico_id=medico_id,
        dia_semana=dia,
        hora_inicio=hora,
        duracion_horas=dur,
        frecuencia_semanas=frec,
        fecha_ancla=ancla,
    )


def test_crear_horario_crea_identidad_y_primera_version(sesion):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    horario = crear_horario(sesion, datos(medico_id=carlos.id), date(2026, 9, 7))
    [version] = sesion.scalars(select(VersionHorario).where(VersionHorario.horario_id == horario.id)).all()
    assert version.medico_id == carlos.id
    assert version.vigente_desde == date(2026, 9, 7)
    assert version.vigente_hasta is None


def test_nueva_version_cierra_la_vigente_y_abre_otra(sesion):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    horario = crear_horario(sesion, datos(medico_id=carlos.id), date(2026, 9, 7))
    nueva = nueva_version(sesion, horario.id, datos(medico_id=carlos.id, hora=time(8)), date(2026, 9, 28))
    versiones = sesion.scalars(
        select(VersionHorario).where(VersionHorario.horario_id == horario.id).order_by(VersionHorario.vigente_desde)
    ).all()
    assert [(v.vigente_desde, v.vigente_hasta, v.hora_inicio) for v in versiones] == [
        (date(2026, 9, 7), date(2026, 9, 28), time(7)),
        (date(2026, 9, 28), None, time(8)),
    ]
    assert nueva.id == versiones[1].id


def test_nueva_version_en_la_misma_fecha_de_inicio_la_rechaza_la_base(sesion):
    horario = crear_horario(sesion, datos(), date(2026, 9, 7))
    with pytest.raises(IntegrityError):
        with sesion.begin_nested():
            nueva_version(sesion, horario.id, datos(hora=time(9)), date(2026, 9, 7))


def test_versiones_en_rango_trae_titular_y_excluye_lo_que_no_toca(sesion):
    florencia = crear_usuario(sesion, "Florencia Lucca")
    vigente = crear_horario(sesion, datos(medico_id=florencia.id, dia=6), date(2026, 9, 7))
    crear_horario(sesion, datos(), date(2026, 9, 7), vigente_hasta=date(2026, 9, 28))
    crear_horario(sesion, datos(), date(2026, 11, 2))

    resultado = versiones_en_rango(sesion, date(2026, 10, 12), date(2026, 10, 18))

    assert [v.horario_id for v in resultado] == [vigente.id]
    assert resultado[0].titular == Titular(florencia.id, "Florencia Lucca")
    assert resultado[0].dia_semana == 6


def test_versiones_en_rango_incluye_la_que_termina_el_dia_de_desde(sesion):
    # Su último día es desde - 1, y un turno de ese día puede entrar en la ventana.
    horario = crear_horario(sesion, datos(dia=7, hora=time(20)), date(2026, 9, 7), vigente_hasta=date(2026, 10, 12))
    resultado = versiones_en_rango(sesion, date(2026, 10, 12), date(2026, 10, 12))
    assert [v.horario_id for v in resultado] == [horario.id]


def test_versiones_en_rango_sin_titular_devuelve_titular_none(sesion):
    crear_horario(sesion, datos(medico_id=None), date(2026, 9, 7))
    [version] = versiones_en_rango(sesion, date(2026, 10, 12), date(2026, 10, 18))
    assert version.titular is None
```

- [ ] **Paso 2: correr y ver que fallan**

Run: `.venv/bin/pytest tests/test_repo_horarios.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.repos'`.

- [ ] **Paso 3: implementar `backend/app/repos/horarios.py`**

Crear vacío `backend/app/repos/__init__.py`.

```python
from dataclasses import asdict, dataclass
from datetime import date, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dominio.calendario import Titular, VersionPlantilla
from app.modelos import HorarioPactado, Usuario, VersionHorario


@dataclass(frozen=True)
class DatosVersion:
    medico_id: int | None
    dia_semana: int
    hora_inicio: time
    duracion_horas: int
    frecuencia_semanas: int
    fecha_ancla: date


def crear_horario(
    sesion: Session, datos: DatosVersion, vigente_desde: date, vigente_hasta: date | None = None
) -> HorarioPactado:
    horario = HorarioPactado()
    sesion.add(horario)
    sesion.flush()
    sesion.add(
        VersionHorario(horario_id=horario.id, vigente_desde=vigente_desde, vigente_hasta=vigente_hasta, **asdict(datos))
    )
    sesion.flush()
    return horario


def nueva_version(sesion: Session, horario_id: int, datos: DatosVersion, desde: date) -> VersionHorario:
    """Cierra la versión vigente en `desde` y abre otra desde esa fecha (D10).

    Si la vigente no se puede cerrar en esa fecha, la rechaza la restricción de la base.
    """
    vigente = sesion.scalars(
        select(VersionHorario)
        .where(VersionHorario.horario_id == horario_id, VersionHorario.vigente_hasta.is_(None))
        .with_for_update()
    ).one_or_none()
    if vigente is not None:
        vigente.vigente_hasta = desde
        sesion.flush()
    nueva = VersionHorario(horario_id=horario_id, vigente_desde=desde, vigente_hasta=None, **asdict(datos))
    sesion.add(nueva)
    sesion.flush()
    return nueva


def versiones_en_rango(sesion: Session, desde: date, hasta: date) -> list[VersionPlantilla]:
    """Versiones que rigen algún día entre desde - 1 (turnos que cruzan medianoche) y hasta."""
    rango = func.daterange(desde - timedelta(days=1), hasta + timedelta(days=1), "[)")
    consulta = (
        select(VersionHorario, Usuario)
        .outerjoin(Usuario, VersionHorario.medico_id == Usuario.id)
        .where(VersionHorario.vigencia.op("&&")(rango))
        .order_by(VersionHorario.horario_id, VersionHorario.vigente_desde)
    )
    return [_a_plantilla(version, medico) for version, medico in sesion.execute(consulta).all()]


def _a_plantilla(version: VersionHorario, medico: Usuario | None) -> VersionPlantilla:
    return VersionPlantilla(
        version_id=version.id,
        horario_id=version.horario_id,
        titular=Titular(medico.id, medico.nombre) if medico is not None else None,
        dia_semana=version.dia_semana,
        hora_inicio=version.hora_inicio,
        duracion_horas=version.duracion_horas,
        frecuencia_semanas=version.frecuencia_semanas,
        fecha_ancla=version.fecha_ancla,
        vigente_desde=version.vigente_desde,
        vigente_hasta=version.vigente_hasta,
    )
```

- [ ] **Paso 4: correr y ver que pasan**

Run: `.venv/bin/pytest -q`
Expected: todas PASS.

- [ ] **Paso 5: commit**

```bash
git add backend/app/repos backend/tests/test_repo_horarios.py
git commit -m "Repositorio de horarios: alta, nueva versión y versiones en rango (D10)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarea 6: GET /api/turnos

**Archivos:**
- Crear: `backend/app/auth.py`, `backend/app/api/turnos.py`
- Modificar: `backend/app/main.py`
- Pruebas: `backend/tests/test_api_turnos.py`

**Interfaces:**
- Consume: `calcular_turnos` y `TurnoCalculado` (tarea 3), `versiones_en_rango`, `crear_horario` y `DatosVersion` (tarea 5), `get_db` (tarea 2), `get_settings` y `ErrorDominio` (tarea 1), y las fixtures `cliente` y `sesion`.
- Produce:
  - `app.auth.usuario_actual() -> None`: enganche para F5.
  - `app.api.turnos.router`.
  - `app.api.turnos.MAX_DIAS_RANGO = 62`.
  - Esquemas `TurnoOut` y `TitularOut` (camelCase).

- [ ] **Paso 1: escribir las pruebas que fallan**

`backend/tests/test_api_turnos.py`:

```python
from datetime import date, time

from app.repos.horarios import DatosVersion, crear_horario
from fabricas import crear_usuario


def horario(sesion, medico_id, dia, hora, dur, frec=1, ancla=date(2026, 9, 7)):
    datos = DatosVersion(
        medico_id=medico_id,
        dia_semana=dia,
        hora_inicio=hora,
        duracion_horas=dur,
        frecuencia_semanas=frec,
        fecha_ancla=ancla,
    )
    return crear_horario(sesion, datos, date(2026, 9, 7))


def test_turnos_formato_exacto(cliente, sesion):
    florencia = crear_usuario(sesion, "Florencia Lucca")
    sabado = horario(sesion, florencia.id, dia=6, hora=time(8), dur=12)

    r = cliente.get("/api/turnos", params={"desde": "2026-10-17", "hasta": "2026-10-17"})

    assert r.status_code == 200
    assert r.json() == [
        {
            "id": f"{sabado.id}:2026-10-17",
            "horarioId": sabado.id,
            "fecha": "2026-10-17",
            "inicio": "2026-10-17T08:00:00-03:00",
            "fin": "2026-10-17T20:00:00-03:00",
            "duracionHoras": 12,
            "titular": {"id": florencia.id, "nombre": "Florencia Lucca"},
        }
    ]


def test_turno_que_cruza_medianoche_aparece_el_dia_siguiente(cliente, sesion):
    carlos = crear_usuario(sesion, "Carlos Lugones")
    viernes = horario(sesion, carlos.id, dia=5, hora=time(20), dur=12)

    r = cliente.get("/api/turnos", params={"desde": "2026-10-17", "hasta": "2026-10-17"})

    [turno] = r.json()
    assert turno["id"] == f"{viernes.id}:2026-10-16"
    assert turno["fin"] == "2026-10-17T08:00:00-03:00"


def test_horario_sin_titular_sale_con_titular_null(cliente, sesion):
    horario(sesion, None, dia=3, hora=time(8), dur=12)
    [turno] = cliente.get("/api/turnos", params={"desde": "2026-10-14", "hasta": "2026-10-14"}).json()
    assert turno["titular"] is None


def test_hasta_anterior_a_desde_es_rango_invalido(cliente):
    r = cliente.get("/api/turnos", params={"desde": "2026-10-18", "hasta": "2026-10-12"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "RANGO_INVALIDO"


def test_rango_de_62_dias_se_acepta_y_63_no(cliente):
    ok = cliente.get("/api/turnos", params={"desde": "2026-10-01", "hasta": "2026-12-01"})
    assert ok.status_code == 200
    grande = cliente.get("/api/turnos", params={"desde": "2026-10-01", "hasta": "2026-12-02"})
    assert grande.status_code == 422
    assert grande.json()["codigo"] == "RANGO_DEMASIADO_GRANDE"


def test_falta_un_parametro_es_error_de_validacion(cliente):
    r = cliente.get("/api/turnos", params={"desde": "2026-10-12"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDACION"


def test_fecha_imposible_es_error_de_validacion(cliente):
    r = cliente.get("/api/turnos", params={"desde": "2026-02-30", "hasta": "2026-03-02"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDACION"


def test_sin_horarios_devuelve_lista_vacia(cliente):
    r = cliente.get("/api/turnos", params={"desde": "2026-10-12", "hasta": "2026-10-18"})
    assert r.status_code == 200
    assert r.json() == []
```

- [ ] **Paso 2: correr y ver que fallan**

Run: `.venv/bin/pytest tests/test_api_turnos.py -q`
Expected: FAIL con 404 `NO_ENCONTRADO` en lugar de 200 o 422.

- [ ] **Paso 3: implementar**

`backend/app/auth.py`:

```python
def usuario_actual() -> None:
    """Punto de enganche para la autenticación (F5).

    En F5 verifica el token de Supabase Auth y devuelve el Usuario. Hasta entonces los endpoints quedan abiertos.
    """
    return None
```

`backend/app/api/turnos.py`:

```python
from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlalchemy.orm import Session

from app.auth import usuario_actual
from app.config import get_settings
from app.db import get_db
from app.dominio.calendario import TurnoCalculado, calcular_turnos
from app.errores import ErrorDominio
from app.repos.horarios import versiones_en_rango

router = APIRouter()

MAX_DIAS_RANGO = 62


class _Esquema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class TitularOut(_Esquema):
    id: int
    nombre: str


class TurnoOut(_Esquema):
    id: str
    horario_id: int
    fecha: date
    inicio: datetime
    fin: datetime
    duracion_horas: int
    titular: TitularOut | None


def _a_salida(turno: TurnoCalculado) -> TurnoOut:
    titular = TitularOut(id=turno.titular.id, nombre=turno.titular.nombre) if turno.titular else None
    return TurnoOut(
        id=turno.id,
        horario_id=turno.horario_id,
        fecha=turno.fecha,
        inicio=turno.inicio,
        fin=turno.fin,
        duracion_horas=turno.duracion_horas,
        titular=titular,
    )


@router.get("/turnos", response_model=list[TurnoOut])
def listar_turnos(
    desde: date,
    hasta: date,
    db: Session = Depends(get_db),
    _usuario: None = Depends(usuario_actual),
) -> list[TurnoOut]:
    """Turnos cuyo intervalo se superpone con [desde 00:00, hasta 24:00) en la zona del servicio (D09, D11)."""
    if hasta < desde:
        raise ErrorDominio("RANGO_INVALIDO", "La fecha 'hasta' no puede ser anterior a 'desde'.")
    if (hasta - desde).days + 1 > MAX_DIAS_RANGO:
        raise ErrorDominio("RANGO_DEMASIADO_GRANDE", f"El rango no puede superar {MAX_DIAS_RANGO} días.")
    versiones = versiones_en_rango(db, desde, hasta)
    turnos = calcular_turnos(versiones, desde, hasta, get_settings().zona)
    return [_a_salida(turno) for turno in turnos]
```

`backend/app/main.py` (reemplazo completo):

```python
from fastapi import APIRouter, FastAPI

from app.api import health, turnos
from app.api.manejadores import registrar_manejadores


def crear_app() -> FastAPI:
    app = FastAPI(title="Guardia Viva", version="0.1.0")
    registrar_manejadores(app)

    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(turnos.router)
    app.include_router(api)
    return app


app = crear_app()
```

- [ ] **Paso 4: correr y ver que pasan**

Run: `.venv/bin/pytest -q`
Expected: todas PASS. Si `test_turnos_formato_exacto` falla porque `inicio` sale con `Z` o sin zona, el problema está en `calcular_turnos` (el `fin` debe volver a la zona del servicio) y no en el esquema.

- [ ] **Paso 5: commit**

```bash
git add backend/app/auth.py backend/app/api/turnos.py backend/app/main.py backend/tests/test_api_turnos.py
git commit -m "GET /api/turnos con turnos calculados e id horarioId:fecha (D09, D11)

Rango máximo de 62 días; JSON en camelCase; endpoint abierto hasta F5.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarea 7: script de datos de ejemplo

**Archivos:**
- Crear: `backend/scripts/__init__.py` (vacío), `backend/scripts/seed.py`
- Pruebas: `backend/tests/test_seed.py`

**Interfaces:**
- Consume: `crear_horario`, `nueva_version`, `DatosVersion` y `versiones_en_rango` (tarea 5), `calcular_turnos` (tarea 3), los modelos (tarea 4) y `SessionLocal` (tarea 2).
- Produce:
  - `scripts.seed.cargar_datos_ejemplo(sesion: Session) -> None`: vacía y recarga, sin commit.
  - `scripts.seed.main(argv: list[str] | None = None) -> int`.

- [ ] **Paso 1: escribir las pruebas que fallan**

`backend/tests/test_seed.py`:

```python
from datetime import date, time
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.dominio.calendario import calcular_turnos
from app.modelos import HorarioPactado, RolUsuario, Usuario, VersionHorario
from app.repos.horarios import versiones_en_rango
from scripts.seed import cargar_datos_ejemplo, main

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def contar(sesion, modelo):
    return sesion.scalar(select(func.count()).select_from(modelo))


def turnos_de(sesion, desde, hasta):
    return calcular_turnos(versiones_en_rango(sesion, desde, hasta), desde, hasta, ZONA)


def test_seed_dos_veces_deja_el_mismo_estado(sesion):
    cargar_datos_ejemplo(sesion)
    primera = [(u.id, u.nombre, u.email, u.rol) for u in sesion.scalars(select(Usuario).order_by(Usuario.id))]
    cargar_datos_ejemplo(sesion)
    segunda = [(u.id, u.nombre, u.email, u.rol) for u in sesion.scalars(select(Usuario).order_by(Usuario.id))]

    assert primera == segunda
    assert contar(sesion, Usuario) == 11
    assert contar(sesion, HorarioPactado) == 14
    assert contar(sesion, VersionHorario) == 15
    assert primera[0][1] == "Florencia Lucca"


def test_seed_tiene_un_coordinador_enzo_sin_horarios(sesion):
    cargar_datos_ejemplo(sesion)
    [enzo] = sesion.scalars(select(Usuario).where(Usuario.rol == RolUsuario.COORDINADOR)).all()
    assert enzo.nombre == "Enzo"
    assert sesion.scalar(select(func.count()).where(VersionHorario.medico_id == enzo.id)) == 0


def test_seed_cubre_la_semana_del_demo_day(sesion):
    cargar_datos_ejemplo(sesion)
    semana = turnos_de(sesion, date(2026, 10, 12), date(2026, 10, 18))

    nombres = {t.titular.nombre for t in semana if t.titular}
    assert {"Florencia Lucca", "Mariano Reimondez", "Carlos Lugones"} <= nombres
    assert len(nombres) == 9  # Javier hace semana por medio y no le toca la semana del 12/10

    assert {6, 8, 12, 24} <= {t.duracion_horas for t in semana}

    florencia_sabado = [
        t for t in semana if t.titular and t.titular.nombre == "Florencia Lucca" and t.fecha == date(2026, 10, 17)
    ]
    assert len(florencia_sabado) == 1

    assert any(t.fin.date() > t.inicio.date() for t in semana if t.fecha >= date(2026, 10, 12))

    jueves = {(t.titular.nombre, t.inicio.time()) for t in semana if t.fecha == date(2026, 10, 15)}
    assert ("Mariano Reimondez", time(14)) in jueves
    assert ("Martín Aguirre", time(8)) in jueves
    assert all(nombre != "Javier Torres" for nombre, _ in jueves)


def test_seed_semana_por_medio_alterna(sesion):
    cargar_datos_ejemplo(sesion)
    jueves_22 = {t.titular.nombre for t in turnos_de(sesion, date(2026, 10, 22), date(2026, 10, 22)) if t.fecha == date(2026, 10, 22)}
    assert "Javier Torres" in jueves_22
    assert "Mariano Reimondez" not in jueves_22
    assert "Martín Aguirre" not in jueves_22


def test_seed_carlos_cambio_de_hora_el_28_de_septiembre(sesion):
    cargar_datos_ejemplo(sesion)

    def martes_de_carlos(dia):
        return [
            t.inicio.time()
            for t in turnos_de(sesion, dia, dia)
            if t.titular and t.titular.nombre == "Carlos Lugones" and t.fecha == dia
        ]

    assert martes_de_carlos(date(2026, 9, 15)) == [time(7)]
    assert martes_de_carlos(date(2026, 10, 13)) == [time(8)]


def test_main_sin_confirmar_no_modifica_nada(capsys):
    assert main([]) == 0
    salida = capsys.readouterr().out
    assert "--confirmar" in salida
```

- [ ] **Paso 2: correr y ver que fallan**

Run: `.venv/bin/pytest tests/test_seed.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'scripts.seed'`.

- [ ] **Paso 3: implementar `backend/scripts/seed.py`**

Crear vacío `backend/scripts/__init__.py`.

```python
"""Datos de ejemplo para desarrollo y demo (docs/guion-demo.md, "Datos de ejemplo necesarios").

Vacía las tablas y vuelve a cargar todo: correrlo dos veces deja el mismo estado y los mismos ids.
Uso, desde backend/: python -m scripts.seed --confirmar
F2 a F4 suman acá la historia, las vacantes y el turno de la vacante urgente.
"""

import argparse
from dataclasses import replace
from datetime import date, time

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modelos import EstadoUsuario, RolUsuario, Usuario
from app.repos.horarios import DatosVersion, crear_horario, nueva_version

DOMINIO_EMAIL = "guardiaviva.test"
INICIO_VIGENCIAS = date(2026, 9, 7)  # lunes; deja lugar a dos semanas de historia antes del Demo Day (F4)
ANCLA_SEMANA_DEMO = date(2026, 10, 12)  # lunes de la semana del Demo Day
ANCLA_SEMANA_PREVIA = date(2026, 10, 5)

MEDICOS = [
    ("Florencia Lucca", "florencia.lucca"),
    ("Mariano Reimondez", "mariano.reimondez"),
    ("Carlos Lugones", "carlos.lugones"),
    ("Valentina Ríos", "valentina.rios"),
    ("Martín Aguirre", "martin.aguirre"),
    ("Lucía Fernández", "lucia.fernandez"),
    ("Diego Sosa", "diego.sosa"),
    ("Paula Méndez", "paula.mendez"),
    ("Javier Torres", "javier.torres"),
    ("Sofía Romero", "sofia.romero"),
]
COORDINADOR = ("Enzo", "enzo")

# (titular, día ISO, inicio, duración en horas, frecuencia en semanas, fecha ancla). El orden fija los ids 1 a 14.
HORARIOS = [
    ("florencia.lucca", 6, time(8), 12, 1, INICIO_VIGENCIAS),  # 1: sábado 17/10
    ("florencia.lucca", 3, time(20), 12, 1, INICIO_VIGENCIAS),  # 2: cruza la medianoche
    ("mariano.reimondez", 1, time(8), 24, 1, INICIO_VIGENCIAS),  # 3: 24 h
    ("mariano.reimondez", 4, time(14), 8, 2, ANCLA_SEMANA_DEMO),  # 4: semana por medio
    ("martin.aguirre", 4, time(8), 24, 2, ANCLA_SEMANA_DEMO),  # 5: alterna con Javier (D14)
    ("javier.torres", 4, time(8), 24, 2, ANCLA_SEMANA_PREVIA),  # 6
    ("carlos.lugones", 2, time(7), 12, 1, INICIO_VIGENCIAS),  # 7: pasa a las 08:00 el 28/9
    ("carlos.lugones", 5, time(20), 12, 1, INICIO_VIGENCIAS),  # 8: cruza la medianoche
    ("valentina.rios", 3, time(8), 12, 1, INICIO_VIGENCIAS),  # 9: se superpone con Sofía
    ("sofia.romero", 3, time(14), 6, 1, INICIO_VIGENCIAS),  # 10: 6 h
    ("lucia.fernandez", 7, time(8), 24, 1, INICIO_VIGENCIAS),  # 11: 24 h
    ("diego.sosa", 6, time(20), 12, 1, INICIO_VIGENCIAS),  # 12: sábado a domingo
    ("paula.mendez", 2, time(20), 12, 1, INICIO_VIGENCIAS),  # 13: cruza la medianoche
    ("paula.mendez", 5, time(8), 12, 1, INICIO_VIGENCIAS),  # 14
]
HORARIO_CON_CAMBIO = 7
FECHA_CAMBIO = date(2026, 9, 28)
NUEVA_HORA = time(8)


def _email(usuario: str) -> str:
    return f"{usuario}@{DOMINIO_EMAIL}"


def cargar_datos_ejemplo(sesion: Session) -> None:
    """Vacía las tablas y carga usuarios y horarios. No hace commit."""
    sesion.execute(text("TRUNCATE usuario, horario_pactado, version_horario RESTART IDENTITY CASCADE"))

    ids: dict[str, int] = {}
    for nombre, usuario in MEDICOS:
        medico = Usuario(nombre=nombre, email=_email(usuario), rol=RolUsuario.MEDICO, estado=EstadoUsuario.ACTIVO)
        sesion.add(medico)
        sesion.flush()
        ids[usuario] = medico.id
    nombre, usuario = COORDINADOR
    sesion.add(Usuario(nombre=nombre, email=_email(usuario), rol=RolUsuario.COORDINADOR, estado=EstadoUsuario.ACTIVO))
    sesion.flush()

    for titular, dia, inicio, duracion, frecuencia, ancla in HORARIOS:
        datos = DatosVersion(
            medico_id=ids[titular],
            dia_semana=dia,
            hora_inicio=inicio,
            duracion_horas=duracion,
            frecuencia_semanas=frecuencia,
            fecha_ancla=ancla,
        )
        horario = crear_horario(sesion, datos, INICIO_VIGENCIAS)
        if horario.id == HORARIO_CON_CAMBIO:
            nueva_version(sesion, horario.id, replace(datos, hora_inicio=NUEVA_HORA), FECHA_CAMBIO)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Carga los datos de ejemplo de Guardia Viva (borra los datos actuales).")
    parser.add_argument("--confirmar", action="store_true", help="confirma que se borran los datos actuales")
    args = parser.parse_args(argv)

    url = make_url(get_settings().database_url)
    print(f"Base de destino: {url.host}:{url.port}/{url.database}")
    if not args.confirmar:
        print("No se modificó nada. Volvé a correrlo con --confirmar para borrar y recargar los datos.")
        return 0

    from app.db import SessionLocal

    with SessionLocal() as sesion, sesion.begin():
        cargar_datos_ejemplo(sesion)
    print(f"Datos de ejemplo cargados: {len(MEDICOS)} médicos, 1 coordinador, {len(HORARIOS)} horarios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Paso 4: correr y ver que pasan**

Run: `.venv/bin/pytest -q`
Expected: todas PASS.

- [ ] **Paso 5: probar el script contra la base local de desarrollo**

Run: `.venv/bin/alembic upgrade head && .venv/bin/python -m scripts.seed --confirmar && .venv/bin/python -m scripts.seed --confirmar`
Expected: las dos corridas imprimen `Datos de ejemplo cargados: 10 médicos, 1 coordinador, 14 horarios.`

Run: `.venv/bin/uvicorn app.main:app --port 8000` en segundo plano y luego `curl -s "localhost:8000/api/turnos?desde=2026-10-17&hasta=2026-10-17"`
Expected: incluye un turno de Florencia Lucca del 17/10 de 08:00 a 20:00. Detener uvicorn después.

- [ ] **Paso 6: commit**

```bash
git add backend/scripts backend/tests/test_seed.py
git commit -m "Script de datos de ejemplo: 10 médicos, coordinador Enzo y 14 horarios

Cubre la guardia de Florencia del 17/10, guardias que cruzan medianoche,
semana por medio (D14) y un cambio de versión.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarea 8: esqueleto de frontend y verificación con Playwright

**Archivos:**
- Crear: `frontend/package.json`, `frontend/index.html`, `frontend/vite.config.js`, `frontend/src/main.jsx`, `frontend/src/App.jsx`, `frontend/playwright.config.js`, `frontend/e2e/health.spec.js`
- Prueba: `frontend/e2e/health.spec.js`

**Interfaces:**
- Consume: `GET /api/health` (tarea 2), que responde `{"estado", "base", "ahora"}` o un error `{"codigo", "mensaje"}`.
- Produce: la página mínima, `npm run dev`, `npm run build` y `npm run test:e2e`.

- [ ] **Paso 1: crear `frontend/package.json` e instalar**

```json
{
  "name": "guardia-viva-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.48.0",
    "@vitejs/plugin-react": "^5.0.0",
    "vite": "^7.0.0"
  }
}
```

Run (desde `frontend/`): `npm install && npx playwright install chromium`
Expected: termina sin errores y se crea `package-lock.json`. Si alguna versión mayor no resuelve, usar la última estable disponible de ese paquete y anotarlo en el reporte de la tarea.

- [ ] **Paso 2: escribir la prueba e2e que falla**

`frontend/playwright.config.js`:

```js
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const BACKEND = fileURLToPath(new URL("../backend", import.meta.url));

// Levanta backend y frontend si no están corriendo. El backend usa backend/.env
// (o el Postgres local de docker-compose si no hay .env).
export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://localhost:5173" },
  webServer: [
    {
      command: ".venv/bin/uvicorn app.main:app --port 8000",
      cwd: BACKEND,
      url: "http://localhost:8000/api/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run dev -- --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
```

`frontend/e2e/health.spec.js`:

```js
import { expect, test } from "@playwright/test";

test("la página muestra el estado del servidor", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Guardia Viva" })).toBeVisible();
  await expect(page.getByTestId("estado")).toHaveText("ok");
  await expect(page.getByTestId("base")).toHaveText("ok");
  await expect(page.getByTestId("ahora")).not.toBeEmpty();
});

test("si el servidor responde con error, se muestra el mensaje", async ({ page }) => {
  await page.route("**/api/health", (ruta) =>
    ruta.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ codigo: "BASE_NO_DISPONIBLE", mensaje: "No se pudo conectar con la base de datos." }),
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("No se pudo conectar con la base de datos.");
});
```

Run: `npm run test:e2e`
Expected: FAIL (todavía no existen `index.html` ni `vite.config.js`).

- [ ] **Paso 3: implementar la página**

`frontend/vite.config.js`:

```js
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
```

`frontend/index.html`:

```html
<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Guardia Viva</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

`frontend/src/main.jsx`:

```jsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

`frontend/src/App.jsx`:

```jsx
import { useEffect, useState } from "react";

export default function App() {
  const [salud, setSalud] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/api/health")
      .then(async (respuesta) => {
        const cuerpo = await respuesta.json().catch(() => ({}));
        if (!respuesta.ok) throw new Error(cuerpo.mensaje ?? `Error ${respuesta.status}`);
        setSalud(cuerpo);
      })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <main>
      <h1>Guardia Viva</h1>
      {error && <p role="alert">No se pudo consultar el servidor: {error}</p>}
      {!salud && !error && <p>Consultando el servidor…</p>}
      {salud && (
        <dl>
          <dt>Estado</dt>
          <dd data-testid="estado">{salud.estado}</dd>
          <dt>Base de datos</dt>
          <dd data-testid="base">{salud.base}</dd>
          <dt>Hora del servidor</dt>
          <dd data-testid="ahora">{salud.ahora}</dd>
        </dl>
      )}
    </main>
  );
}
```

- [ ] **Paso 4: correr la prueba e2e y la compilación**

Postgres de docker-compose levantado y migrado (`docker compose up -d --wait` en la raíz; `.venv/bin/alembic upgrade head` en `backend/`).

Run (desde `frontend/`): `npm run test:e2e && npm run build`
Expected: 2 pruebas PASS y la compilación genera `frontend/dist/`, que está ignorado por git.

- [ ] **Paso 5: commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/index.html frontend/vite.config.js frontend/src frontend/playwright.config.js frontend/e2e
git commit -m "Esqueleto del frontend con React y Vite que consulta GET /api/health (D05)

Verificación con Playwright como dependencia de desarrollo.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tarea 9: documentación

**Archivos:**
- Crear: `backend/CLAUDE.md`, `frontend/CLAUDE.md`
- Modificar: `CLAUDE.md` (secciones "Diseño > Endpoints principales", "Contrato entre interfaz y servidor" y "Comandos"), `docs/decisiones-arquitectura.md` (D10), `docs/prompts-principales.md` (entrada 3)

**Interfaces:**
- Consume: los comandos y convenciones de las tareas 1 a 8.
- Produce: documentación; no hay código.

- [ ] **Paso 1: crear `backend/CLAUDE.md`**

````markdown
# Backend de Guardia Viva

FastAPI + SQLAlchemy 2 + Alembic sobre Postgres. Leer también el CLAUDE.md de la raíz y `docs/decisiones-arquitectura.md`.

## Estructura

1. `app/dominio/`: lógica pura, sin base de datos ni FastAPI. Se prueba con pruebas unitarias.
2. `app/modelos/`: tablas SQLAlchemy. El esquema real lo define la migración de Alembic (SQL escrito a mano); los modelos deben coincidir con ella.
3. `app/repos/`: consultas. No hacen commit; trabajan dentro de la transacción de quien llama.
4. `app/api/`: routers bajo el prefijo `/api`. Los esquemas de respuesta usan alias camelCase.
5. `app/errores.py`: `ErrorDominio(codigo, mensaje, status)`. `app/api/manejadores.py` lo convierte en `{"codigo", "mensaje"}`.
6. `app/reloj.py`: reloj inyectable (D27). Nada fuera de ese archivo consulta la hora del sistema; una prueba lo verifica.
7. `app/auth.py`: `usuario_actual`, enganche para la autenticación de F5.
8. `scripts/seed.py`: datos de ejemplo.

## Convenciones

1. Lo que depende de "ahora" recibe el reloj con `Depends(get_reloj)`; en las pruebas se usa la fixture `reloj` (`RelojFijo`).
2. Los errores de dominio se lanzan como `ErrorDominio` con un código en MAYÚSCULAS_CON_GUIONES.
3. Cada cambio de esquema es una migración nueva en `migrations/versions/`, escrita en SQL con `op.execute`.
4. Las pruebas usan la fixture `sesion` (transacción que se deshace) y `cliente` (TestClient con esa sesión). Las pruebas de concurrencia se marcan `@pytest.mark.commit_real` y usan `fabrica_sesiones`; la base se vacía al terminar.

## Comandos (desde backend/)

```bash
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # una vez
cp .env.example .env                                            # completar DATABASE_URL con el Session pooler de Supabase
docker compose up -d --wait                                     # desde la raíz: Postgres 15 local (puerto 5433)
.venv/bin/pytest                                                # pruebas (siempre contra el Postgres local)
.venv/bin/alembic upgrade head                                  # migrar la base de DATABASE_URL
.venv/bin/python -m scripts.seed --confirmar                    # borrar y cargar los datos de ejemplo
.venv/bin/uvicorn app.main:app --reload --port 8000             # levantar la API; OpenAPI en /docs
```
````

- [ ] **Paso 2: crear `frontend/CLAUDE.md`**

````markdown
# Frontend de Guardia Viva

React + Vite, en JavaScript. Las pantallas reales se hacen en F6; el prototipo HTML de la raíz (`index.html`) es solo referencia visual y no se reutiliza su código.

## Convenciones

1. Toda llamada al servidor va a `/api/...`. En desarrollo, Vite la redirige a `http://localhost:8000`; en producción, el backend sirve la compilación (F6).
2. Los errores del servidor llegan como `{"codigo", "mensaje"}`: la interfaz decide por `codigo` y muestra `mensaje`.
3. El JSON viene en camelCase.

## Comandos (desde frontend/)

```bash
npm install && npx playwright install chromium   # una vez
npm run dev                                      # http://localhost:5173 (necesita el backend en el puerto 8000)
npm run build                                    # compila en dist/
npm run test:e2e                                 # Playwright; levanta backend y frontend si no están corriendo
```
````

- [ ] **Paso 3: actualizar `CLAUDE.md` de la raíz**

En "Endpoints principales", agregar al comienzo de la lista, antes de "1. Sesión", la línea:

```markdown
Todos los endpoints van bajo el prefijo `/api` (por ejemplo, `GET /api/turnos`); el OpenAPI queda en `/docs`.
```

En "Contrato entre interfaz y servidor", agregar como ítem 5:

```markdown
5. JSON en camelCase (por ejemplo, `horarioId`, `duracionHoras`). Instantes en ISO 8601 con desplazamiento (`2026-10-17T08:00:00-03:00`).
```

Reemplazar la sección "Comandos" (la línea "(Completar cuando exista el esqueleto...)") por:

````markdown
## Comandos

Detalle en `backend/CLAUDE.md` y `frontend/CLAUDE.md`.

```bash
docker compose up -d --wait                                            # Postgres 15 local para pruebas (puerto 5433)
cd backend && .venv/bin/pytest                                         # pruebas del backend
cd backend && .venv/bin/alembic upgrade head                           # migrar (DATABASE_URL de backend/.env)
cd backend && .venv/bin/python -m scripts.seed --confirmar             # cargar datos de ejemplo (borra los actuales)
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000      # levantar el backend
cd frontend && npm run dev                                             # levantar el frontend
cd frontend && npm run test:e2e                                        # verificación con Playwright
```

El reinicio de la demo es el mismo script de datos de ejemplo; en F2 a F4 suma historia y vacantes.
````

- [ ] **Paso 4: corregir D10 en `docs/decisiones-arquitectura.md`**

Reemplazar el párrafo que empieza con "D10. Plantilla como horarios pactados versionados:" hasta "(restricción de exclusión de Postgres)." por:

```markdown
D10. Plantilla como horarios pactados versionados: HorarioPactado (identidad estable) y VersionHorario (médico titular, opcional para los horarios sin titular de D24; día de la semana, hora de inicio, duración, frecuencia en semanas, fecha ancla, vigenteDesde, vigenteHasta). Una renegociación o un cambio de titular cierra la versión vigente y abre otra. Las vigencias de un horario no se superponen (restricción de exclusión de Postgres).
```

Agregar al final del párrafo (después de "Alternativa descartada: ...") la línea:

```markdown
Ajuste del 5/10/2026 (spec de F0 y F1): el texto anterior decía que el HorarioPactado pertenecía a un médico; el médico va en la versión, como ya indicaban D24 y CLAUDE.md.
```

- [ ] **Paso 5: completar la entrada 3 de `docs/prompts-principales.md`**

Reemplazar las líneas `Fecha: completar al usarlo.` y `Resultado: completar (spec y plan generados, PR).` de la entrada 3 por:

```markdown
Fecha: 5/10/2026.
```

```markdown
Resultado: spec en `docs/superpowers/specs/2026-10-05-f0-f1-esqueleto-plantilla-calendario-design.md` y plan en `docs/superpowers/plans/2026-10-05-f0-f1-esqueleto-plantilla-calendario.md`. Preguntas del agente antes del spec: herramienta de entorno de Python (venv + pip), autenticación en F1 (abierto hasta F5), granularidad de horarios (inicio HH:MM, duración en horas enteras). El agente señaló una inconsistencia en D10 (médico en el horario o en la versión), que se corrigió. Durante el diseño el equipo agregó el marcador commit_real para las pruebas de concurrencia de F3. Implementación por subagentes con Sonnet en la branch feature/esqueleto-calendario.
```

- [ ] **Paso 6: verificación final y commit**

Run (desde `backend/`): `.venv/bin/pytest -q`
Expected: todas PASS.

Run (desde `frontend/`): `npm run test:e2e`
Expected: 2 PASS.

```bash
git add CLAUDE.md backend/CLAUDE.md frontend/CLAUDE.md docs/decisiones-arquitectura.md docs/prompts-principales.md
git commit -m "Documentación de F0 y F1: comandos, CLAUDE.md por nivel y corrección de D10

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

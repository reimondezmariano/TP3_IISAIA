# Backend de Guardia Viva

FastAPI + SQLAlchemy 2 + Alembic sobre Postgres. Leer también el CLAUDE.md de la raíz y `docs/decisiones-arquitectura.md`.

## Estructura

1. `app/dominio/`: lógica pura, sin base de datos ni FastAPI. Se prueba con pruebas unitarias.
2. `app/modelos/`: tablas SQLAlchemy. El esquema real lo define la migración de Alembic (SQL escrito a mano); los modelos deben coincidir con ella.
3. `app/repos/`: consultas. No hacen commit; trabajan dentro de la transacción de quien llama.
4. `app/api/`: routers bajo el prefijo `/api`. Los esquemas de respuesta usan alias camelCase.
5. `app/errores.py`: `ErrorDominio(codigo, mensaje, status)`. `app/api/manejadores.py` lo convierte en `{"codigo", "mensaje"}`.
6. `app/reloj.py`: reloj inyectable (D27). Nada fuera de ese archivo consulta la hora del sistema; una prueba lo verifica.
7. `app/auth.py`: verificación del token de Supabase Auth (D06) y dependencias de permisos: `identidad_actual` (token válido), `usuario_registrado` (solo GET /me), `usuario_actual` (cuenta ACTIVA; la exige todo endpoint salvo /health, /me y /registro) y `requiere_coordinador`.
8. `scripts/seed.py`: datos de ejemplo. Al recargar conserva, por email, las cuentas de Supabase Auth de los usuarios de ejemplo; los usuarios que no son de ejemplo se borran.

## Convenciones

1. Lo que depende de "ahora" recibe el reloj con `Depends(get_reloj)`; en las pruebas se usa la fixture `reloj` (`RelojFijo`).
2. Los errores de dominio se lanzan como `ErrorDominio` con un código en MAYÚSCULAS_CON_GUIONES.
3. Cada cambio de esquema es una migración nueva en `migrations/versions/`, escrita en SQL con `op.execute`.
4. Las pruebas usan la fixture `sesion` (transacción que se deshace) y `cliente` (TestClient con esa sesión). Las pruebas de concurrencia se marcan `@pytest.mark.commit_real` y usan `fabrica_sesiones`; la base se vacía al terminar.
5. Configuración de pytest en `pyproject.toml`: `pythonpath = ["."]` (para importar el paquete `scripts`) y un filtro que silencia el aviso de Starlette por usar `httpx` en el TestClient (pide `httpx2`). Pendiente: migrar a httpx2 y quitar el filtro.
6. `alembic.ini` usa un solo `%` en el formato de log y `path_separator = os`; no volver a `%%`, que imprime el texto literal.
7. Pruebas con sesión: `crear_usuario` crea usuarios con cuenta de Supabase (`con_cuenta=False` para simular los del seed) y `encabezados(usuario)` arma el `Authorization: Bearer`. La fixture `cliente` verifica tokens con `SECRETO_PRUEBA`; `token_para(...)` arma tokens a medida (vencidos, sin email, otro algoritmo).
8. Los instantes de dominio (`creada_en` de vacante, postulación y notificación; `ocurrido_en` del evento; `cerrada_en`, `consolidado_en`, etc.) no tienen valor por defecto en la base: se completan con `reloj.ahora()`. Excepción: `turno.creado_en` es una marca técnica con `DEFAULT now()` (hora real de la base); no usarla en la lógica de dominio como "cuándo se materializó el turno".
9. `evento_turno` solo admite INSERT: un trigger rechaza UPDATE y DELETE (D22). TRUNCATE sigue funcionando para el seed y las pruebas.
10. El vencimiento del token se controla con la hora real dentro de PyJWT, no con el reloj inyectable, para que adelantar el reloj de demo no cierre las sesiones.

## Comandos (desde backend/)

```bash
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # una vez
cp .env.example .env                                            # completar DATABASE_URL con el Session pooler de Supabase
# completar también SUPABASE_URL (o SUPABASE_JWT_SECRET) y CODIGO_COORDINACION; en Supabase, Authentication > Sign In / Providers > Email: desactivar "Confirm email" (D06)
docker compose up -d --wait                                     # desde la raíz: Postgres 15 local (puerto 5433)
.venv/bin/pytest                                                # pruebas (siempre contra el Postgres local)
.venv/bin/alembic upgrade head                                  # migrar la base de DATABASE_URL
.venv/bin/python -m scripts.seed --confirmar                    # borrar y cargar los datos de ejemplo
.venv/bin/uvicorn app.main:app --reload --port 8000             # levantar la API; OpenAPI en /docs
```

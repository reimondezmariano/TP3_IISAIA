# F0 + F1: esqueleto, plantilla y calendario

Fecha: 5/10/2026. Branch: `feature/esqueleto-calendario`.
Decisiones aplicadas: D02 a D05, D07, D09 a D14, D23, D24, D27. Fuente: `docs/decisiones-arquitectura.md`.

## Objetivo

Dejar funcionando el esqueleto del sistema (backend FastAPI conectado a Postgres, frontend React mínimo, pruebas contra Postgres) y el primer flujo de dominio: los turnos se calculan desde la plantilla de horarios pactados y se consultan con `GET /api/turnos`.

Criterio de éxito: con la base cargada por el script de datos de ejemplo, `GET /api/turnos?desde=2026-10-12&hasta=2026-10-18` devuelve las guardias de la semana del Demo Day de los 10 médicos, con duraciones de 6, 8, 12 y 24 h, un horario semana por medio, guardias que cruzan la medianoche y la guardia de Florencia del sábado 17/10. Todas las pruebas pasan contra Postgres 15.

## Fuera de alcance

1. Autenticación: `GET /api/turnos` queda abierto en este ciclo y se protege en F5. Se deja una dependencia `usuario_actual` sin implementar como punto de enganche.
2. Escritura de horarios por API (`POST /horarios` y versiones): llega con staff en F5. En este ciclo la plantilla solo la escribe el script de datos de ejemplo.
3. Semáforo, etiqueta BAJA, turnos materializados, vacantes: F2 en adelante.
4. Endpoint del reloj de demo (`POST /demo/reloj`) y `RelojDemo`: F4.
5. Servir la compilación del frontend como estáticos y PWA: F6.

## Decisiones técnicas de este ciclo

1. Entorno de Python: `venv` + `pip` con `pyproject.toml` (`pip install -e ".[dev]"`). Python 3.12.
2. Cálculo de turnos en una función de dominio pura en Python (enfoque A). Se descartó calcular en SQL con `generate_series`: la regla de frecuencia quedaba difícil de probar y la combinación con turnos materializados en F2 terminaría igual en Python.
3. Toda la API va bajo el prefijo `/api`, para que en F6 los estáticos se sirvan desde `/` sin choques.
4. JSON en camelCase mediante alias de Pydantic.
5. Hora de inicio con minutos (`TIME`), duración en horas enteras de 1 a 24.
6. Día de la semana ISO: 1 = lunes, 7 = domingo.
7. Vigencias semiabiertas `[vigente_desde, vigente_hasta)`; `vigente_hasta` vacío significa vigente.
8. Pruebas contra Postgres 15 local en docker-compose. Supabase (Session pooler, cadena en `.env` fuera del repo) queda para desarrollo y demo.
9. Frontend en JavaScript (sin TypeScript).

## Estructura

```
docker-compose.yml          # Postgres 15 para pruebas, puerto 5433
backend/
  pyproject.toml
  CLAUDE.md
  .env.example              # DATABASE_URL, TEST_DATABASE_URL, APP_TIMEZONE, MODO_DEMO
  alembic.ini
  migrations/
  app/
    main.py                 # crea la app, routers bajo /api, manejadores de error
    config.py               # pydantic-settings, lee .env
    db.py                   # engine, dependencia get_db (sesión por pedido)
    reloj.py                # Reloj, RelojSistema, RelojFijo, dependencia get_reloj
    errores.py              # ErrorDominio y formato {codigo, mensaje}
    auth.py                 # usuario_actual: punto de enganche para F5, sin implementar
    dominio/
      calendario.py         # calcular_turnos, formatear_id_turno, parsear_id_turno
    modelos/                # tablas SQLAlchemy
    repos/                  # consultas (versiones vigentes, nueva_version)
    api/
      health.py
      turnos.py
  scripts/
    seed.py
  tests/
frontend/
  package.json
  vite.config.js            # proxy /api → http://localhost:8000
  CLAUDE.md
  src/App.jsx               # consulta /api/health y muestra el resultado
```

`.env` está en `.gitignore`. `.env.example` documenta cada variable sin valores secretos.

## Componentes del esqueleto (F0)

### Configuración

`config.py` lee con pydantic-settings:
1. `DATABASE_URL`: Postgres de desarrollo (Supabase vía Session pooler) o local.
2. `TEST_DATABASE_URL`: por defecto, el contenedor de docker-compose.
3. `APP_TIMEZONE`: por defecto `America/Argentina/Buenos_Aires`.
4. `MODO_DEMO`: booleano, por defecto falso (lo usa F4).

### Reloj inyectable (D27)

1. `Reloj` es un protocolo con `ahora() -> datetime`, que devuelve un `datetime` con zona horaria en la del servicio.
2. `RelojSistema` es la implementación real. Es el único lugar del código que consulta la hora del sistema.
3. `RelojFijo(instante)` sirve para las pruebas y admite `avanzar(timedelta)`.
4. Se inyecta con `Depends(get_reloj)`; en las pruebas se reemplaza con `app.dependency_overrides`.
5. Una prueba recorre `app/` y falla si encuentra `datetime.now`, `datetime.utcnow`, `date.today` o `time.time` fuera de `reloj.py`.

### Errores

1. `ErrorDominio(codigo, mensaje, status)` es la excepción base para errores de dominio y de validación propia.
2. Un manejador global responde `{"codigo": "...", "mensaje": "..."}` con el status correspondiente.
3. Los errores de validación de FastAPI (`RequestValidationError`) se reescriben al mismo formato con `codigo: "VALIDACION"` y status 422.
4. Status según CLAUDE.md: 401, 403, 404, 409 y 422.

### GET /api/health

1. Ejecuta `SELECT 1` contra la base.
2. Si responde, devuelve 200 con `{"estado": "ok", "base": "ok", "ahora": "<ISO 8601 del reloj>"}`.
3. Si la base no responde, devuelve 503 con `{"codigo": "BASE_NO_DISPONIBLE", "mensaje": "..."}`.

### Frontend

1. Vite + React en `frontend/`, con `package.json`.
2. En desarrollo, el proxy de Vite manda `/api` a `http://localhost:8000`.
3. `App.jsx` muestra el título "Guardia Viva" y el resultado de `GET /api/health`: estado, estado de la base y hora del servidor, o un mensaje de error si no responde.
4. Las pantallas reales son de F6.
5. Si la verificación con Playwright necesita instalar algo, va como dependencia de desarrollo del frontend.

### Infraestructura de pruebas

1. `docker compose up -d` levanta Postgres 15 en el puerto 5433.
2. Al inicio de la sesión de pytest se recrea la base de prueba y se corre `alembic upgrade head`, así las migraciones también quedan probadas.
3. Por defecto, cada prueba corre dentro de una transacción que se deshace al terminar. La sesión de la aplicación se reemplaza para que use esa misma conexión.
4. Las pruebas marcadas con `@pytest.mark.commit_real` (lo necesitan las pruebas de concurrencia de F3, con dos conexiones simultáneas) no usan esa transacción: reciben una fábrica de sesiones que confirma de verdad. Al terminar, un fixture ejecuta `TRUNCATE ... RESTART IDENTITY CASCADE` sobre todas las tablas menos `alembic_version`. Este ciclo incluye una prueba de ejemplo que usa el marcador.
5. El marcador se registra en la configuración de pytest, para que un error de tipeo en su nombre falle.

## Modelo de datos (F1)

Una migración de Alembic. Las partes que Alembic no genera solo (extensión, columna generada, exclusión, RLS) se escriben a mano en la migración.

### Extensión

`CREATE EXTENSION IF NOT EXISTS btree_gist;`, necesaria para la restricción de exclusión que combina igualdad y rangos.

### usuario

| Columna | Tipo | Reglas |
|---|---|---|
| id | serial | PK |
| nombre | text | obligatorio |
| email | text | obligatorio; índice único sobre `lower(email)` |
| rol | enum `rol_usuario` (MEDICO, COORDINADOR) | obligatorio |
| estado | enum `estado_usuario` (PENDIENTE, ACTIVO, BAJA) | obligatorio, por defecto PENDIENTE |
| fecha_baja | date | opcional |
| auth_id | uuid | opcional, único; se completa en F5 al vincular con Supabase Auth |
| creado_en | timestamptz | obligatorio, por defecto `now()` |

No hay CHECK entre `estado` y `fecha_baja`: una baja con fecha futura (D24, activo hasta ese día inclusive) la haría incómoda. Esa regla se resuelve en F5.

### horario_pactado

| Columna | Tipo | Reglas |
|---|---|---|
| id | serial | PK |
| creado_en | timestamptz | obligatorio, por defecto `now()` |

Es la identidad estable del horario (D09, D10). El id del turno no cambia aunque cambien el médico, el día o la hora.

### version_horario

| Columna | Tipo | Reglas |
|---|---|---|
| id | serial | PK |
| horario_id | int | FK a horario_pactado, obligatorio |
| medico_id | int | FK a usuario, **opcional** (vacío = sin titular, D24) |
| dia_semana | smallint | CHECK entre 1 y 7 (ISO, 1 = lunes) |
| hora_inicio | time | obligatorio |
| duracion_horas | smallint | CHECK entre 1 y 24 |
| frecuencia_semanas | smallint | CHECK ≥ 1 |
| fecha_ancla | date | CHECK `extract(isodow from fecha_ancla) = 1` (lunes, D14) |
| vigente_desde | date | obligatorio |
| vigente_hasta | date | opcional; CHECK `vigente_hasta > vigente_desde` |
| vigencia | daterange | columna generada: `daterange(vigente_desde, vigente_hasta, '[)')` |

Restricción de exclusión (D10): `EXCLUDE USING gist (horario_id WITH =, vigencia WITH &&)`. Dos versiones del mismo horario nunca se superponen; horarios distintos sí pueden superponerse.

Reglas que no van en la base y se validan en el backend cuando exista escritura por API (F5):
1. el médico de una versión tiene rol MEDICO;
2. un coordinador no tiene horarios (D23);
3. una versión nueva cierra la anterior.

### Cambio de versión

`repos.horarios.nueva_version(sesion, horario_id, datos, desde)`:
1. Cierra la versión vigente en `desde`, con `vigente_hasta = desde`.
2. Crea la versión nueva con `vigente_desde = desde` y `vigente_hasta` vacío.
3. Lo hace dentro de la transacción de quien llama. Si la vigente no puede cerrarse en esa fecha (por ejemplo, `desde ≤ vigente_desde`), la restricción de la base rechaza el cambio.
4. Lo usan el script de datos de ejemplo y las pruebas, y F5 lo reutiliza.

### RLS (D07)

La migración ejecuta `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` en `usuario`, `horario_pactado` y `version_horario`, sin políticas. El backend se conecta como dueño de las tablas, así que RLS no lo afecta.

## Cálculo de turnos (F1)

### Función de dominio

En `app/dominio/calendario.py`, sin dependencias de base de datos ni de FastAPI:

```python
def calcular_turnos(versiones: list[VersionPlantilla], desde: date, hasta: date,
                    zona: ZoneInfo) -> list[TurnoCalculado]
```

`VersionPlantilla` es una dataclass inmutable con los datos de la versión y el titular (id y nombre, o `None`). El repositorio la construye a partir de las filas.

Algoritmo:
1. La ventana es `[inicio_ventana, fin_ventana)`: desde las 00:00 de `desde` hasta las 00:00 de `hasta + 1 día`, en la zona horaria del servicio.
2. Las fechas candidatas van de `desde − 1 día` a `hasta`. Como la duración máxima es 24 h, ningún turno que empiece antes de `desde − 1` puede tocar la ventana.
3. Para cada versión y cada fecha candidata `f`, hay turno si se cumplen las tres condiciones:
   1. `f.isoweekday() == dia_semana`;
   2. `vigente_desde ≤ f` y (`vigente_hasta` vacío o `f < vigente_hasta`). La vigencia se evalúa sobre la fecha de inicio, porque el turno pertenece a la fecha en que empieza (D13);
   3. `((lunes(f) − fecha_ancla).days // 7) % frecuencia_semanas == 0`, donde `lunes(f)` es el lunes de la semana de `f`. El `%` de Python da resultados correctos también para fechas anteriores al ancla.
4. `inicio = datetime.combine(f, hora_inicio, tzinfo=zona)`.
5. `fin` se calcula sumando la duración en UTC y volviendo a la zona del servicio, para que sea correcto aun si algún día vuelve el horario de verano.
6. El turno se incluye solo si se superpone con la ventana: `inicio < fin_ventana` y `fin > inicio_ventana`. Un turno que termina exactamente a las 00:00 de `desde` no se incluye.
7. Orden: por `inicio` y, a igualdad de inicio, por `horario_id`.

`TurnoCalculado` es una dataclass inmutable con estos campos:
1. `id`: texto con la forma `"horarioId:fecha"` (D09);
2. `horario_id`;
3. `fecha`: la fecha de inicio;
4. `inicio`;
5. `fin`;
6. `duracion_horas`;
7. `version_id`: no sale en la API, pero F2 lo usa para el snapshot (D11);
8. `titular`: id y nombre, o `None`.

### Identificador de turno (D09)

En el mismo módulo:
1. `formatear_id_turno(horario_id, fecha) -> str` devuelve, por ejemplo, `"7:2026-10-17"`.
2. `parsear_id_turno(texto) -> (horario_id, fecha)`. Si el texto no tiene ese formato, lanza `ErrorDominio("TURNO_ID_INVALIDO", ..., 422)`.

### Repositorio

`repos.horarios.versiones_en_rango(sesion, desde, hasta)` trae las versiones cuya `vigencia` se superpone con `daterange(desde − 1, hasta + 1, '[)')`, con un join opcional al usuario para tener el nombre del titular. Devuelve una lista de `VersionPlantilla`.

### GET /api/turnos

Parámetros: `desde` y `hasta`, obligatorios, en formato ISO (`YYYY-MM-DD`).

Validaciones:
1. Si `hasta < desde`, responde 422 `RANGO_INVALIDO`.
2. Si el rango tiene más de 62 días (`hasta − desde + 1 > 62`), responde 422 `RANGO_DEMASIADO_GRANDE`.
3. Si falta un parámetro o la fecha está mal formada, responde 422 `VALIDACION`.

Respuesta 200, una lista ordenada como en el algoritmo:

```json
[
  {
    "id": "7:2026-10-17",
    "horarioId": 7,
    "fecha": "2026-10-17",
    "inicio": "2026-10-17T08:00:00-03:00",
    "fin": "2026-10-17T20:00:00-03:00",
    "duracionHoras": 12,
    "titular": {"id": 3, "nombre": "Florencia Lucca"}
  }
]
```

Si el horario no tiene titular, `titular` sale como `null`. F2 agrega campos (estado del semáforo, etiqueta BAJA) sin romper este contrato.

## Script de datos de ejemplo (F1)

Se ejecuta con `python -m scripts.seed --confirmar` desde `backend/`, contra `DATABASE_URL`.

1. Muestra el host y la base a los que apunta. Sin `--confirmar` no modifica nada y termina con un mensaje.
2. En una sola transacción ejecuta `TRUNCATE usuario, horario_pactado, version_horario RESTART IDENTITY CASCADE` y vuelve a cargar todo. Correrlo dos veces deja el mismo estado, con los mismos ids.
3. F2 a F4 van a extender este mismo script con historia, vacantes y el turno preparado para la vacante urgente.

### Usuarios

Todos en estado ACTIVO. Emails con la forma `nombre.apellido@guardiaviva.test`; la vinculación con Supabase Auth es de F5.

1. Médicos del equipo: Florencia Lucca, Mariano Reimondez y Carlos Lugones.
2. Médicos ficticios: Valentina Ríos, Martín Aguirre, Lucía Fernández, Diego Sosa, Paula Méndez, Javier Torres y Sofía Romero.
3. Coordinador: Enzo (`enzo@guardiaviva.test`).

### Horarios

Vigencias desde el lunes 7/9/2026, para que en F4 entren las dos semanas de historia previas al Demo Day. Fecha ancla 7/9/2026 salvo que se indique otra.

| # | Médico | Día | Inicio | Duración (h) | Frecuencia | Qué cubre |
|---|---|---|---|---|---|---|
| 1 | Florencia | sábado | 08:00 | 12 | 1 | guardia del sábado 17/10 |
| 2 | Florencia | miércoles | 20:00 | 12 | 1 | cruza la medianoche en la semana del Demo Day |
| 3 | Mariano | lunes | 08:00 | 24 | 1 | 24 h, cruza la medianoche |
| 4 | Mariano | jueves | 14:00 | 8 | 2, ancla 12/10/2026 | semana por medio; cae en la semana del Demo Day |
| 5 | Martín | jueves | 08:00 | 24 | 2, ancla 12/10/2026 | dos médicos alternan el mismo hueco (D14)… |
| 6 | Javier | jueves | 08:00 | 24 | 2, ancla 5/10/2026 | …desfasados una semana |
| 7 | Carlos | martes | 08:00 | 12 | 1 | cambio de versión: hasta el 28/9/2026 empezaba a las 07:00 |
| 8 | Carlos | viernes | 20:00 | 12 | 1 | cruza la medianoche |
| 9 | Valentina | miércoles | 08:00 | 12 | 1 | se superpone con Sofía |
| 10 | Sofía | miércoles | 14:00 | 6 | 1 | 6 h |
| 11 | Lucía | domingo | 08:00 | 24 | 1 | 24 h |
| 12 | Diego | sábado | 20:00 | 12 | 1 | cruza del sábado al domingo |
| 13 | Paula | martes | 20:00 | 12 | 1 | cruza la medianoche |
| 14 | Paula | viernes | 08:00 | 12 | 1 | |

El horario 7 se carga con dos versiones: la primera, de las 07:00, vigente `[7/9/2026, 28/9/2026)`; la segunda, de las 08:00, desde el 28/9/2026 sin fin. La segunda se crea con `nueva_version`.

## Pruebas

### Unitarias del dominio (sin base)

1. Un horario semanal genera un turno por semana en el día correcto.
2. Semana por medio: genera turnos en las semanas que cumplen la frecuencia y salta las otras, también para fechas anteriores al ancla.
3. Medianoche: un turno de 22:00 a 06:00 del lunes aparece al consultar el lunes y también al consultar el martes.
4. Un turno de 24 h aparece en los dos días que toca.
5. Un turno que termina exactamente a las 00:00 de `desde` no aparece.
6. Superposición entre médicos: dos horarios distintos con el mismo intervalo generan dos turnos.
7. Cambio de versión: los turnos anteriores a la fecha de cambio usan la versión vieja y los posteriores la nueva. Esto vale también si la versión nueva cambia el día de la semana. El `horario_id`, y por lo tanto la forma del id, se mantiene.
8. Un turno que empieza el último día de vigencia de una versión y termina después de su `vigente_hasta` pertenece a la versión vieja.
9. Una versión sin titular genera turnos con `titular` en `None`.
10. Orden por inicio y, a igualdad, por `horario_id`.
11. `formatear_id_turno` y `parsear_id_turno` son inversas; un texto mal formado produce `TURNO_ID_INVALIDO`.

### Integración (Postgres 15)

1. La migración se aplica sobre una base vacía.
2. La exclusión rechaza dos versiones superpuestas del mismo horario y acepta dos contiguas `[a, b)` y `[b, ∞)`. También acepta versiones superpuestas de horarios distintos.
3. Los CHECK rechazan una fecha ancla que no es lunes, una duración de 0 o de 25 h y un `vigente_hasta ≤ vigente_desde`.
4. El email es único sin distinguir mayúsculas.
5. `nueva_version` cierra la vigente y crea la nueva.
6. `GET /api/turnos` de punta a punta: devuelve los turnos con el formato del contrato y los 422 (`RANGO_INVALIDO`, `RANGO_DEMASIADO_GRANDE`, `VALIDACION`) con el formato de error.
7. `GET /api/health` con `RelojFijo` devuelve la hora del reloj.
8. Una prueba de ejemplo con `@pytest.mark.commit_real` confirma datos desde dos sesiones y verifica que la base queda vacía después.
9. El script de datos de ejemplo, corrido dos veces contra la base de prueba, deja el mismo estado. Además, para la semana del 12 al 18/10/2026 se verifica que existen:
   1. la guardia de Florencia del sábado 17/10;
   2. al menos una guardia que cruza la medianoche;
   3. la guardia de Mariano del jueves 15/10, semana por medio;
   4. el turno del martes de Carlos a las 08:00, y a las 07:00 si se consulta una semana anterior al 28/9.
10. Ningún archivo de `app/` llama a la hora del sistema fuera de `reloj.py`.

### Interfaz

Verificación con Playwright, con el backend y el frontend levantados: la página muestra "Guardia Viva" y el estado `ok` de `/api/health`.

## Documentación en el mismo PR

1. `CLAUDE.md` de la raíz: indicar que los endpoints van bajo el prefijo `/api` y completar la sección Comandos (levantar el backend y el frontend, correr las pruebas, migrar, cargar los datos de ejemplo).
2. `backend/CLAUDE.md` y `frontend/CLAUDE.md`: estructura, convenciones (reloj inyectable, formato de error, camelCase) y comandos.
3. `docs/decisiones-arquitectura.md`, D10: corregir el texto para que el médico quede en VersionHorario (opcional, D24) y no en HorarioPactado, como ya dicen CLAUDE.md y D24.
4. `docs/prompts-principales.md`, entrada 3: fecha y resultado.

## Notas para la implementación

1. Los subagentes que implementan usan Sonnet, para ahorrar tokens (`docs/plan-de-implementacion.md`, "Consumo de tokens").
2. Si la verificación con Playwright requiere instalar algo, va como dependencia de desarrollo del frontend.
3. Antes de dar el trabajo por terminado: correr todas las pruebas y verificar la interfaz con Playwright.

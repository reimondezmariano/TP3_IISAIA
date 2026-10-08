# Guardia Viva

Aplicación para gestionar las guardias médicas de un servicio hospitalario de 10 a 12 médicos. Reemplaza un grupo de WhatsApp y una planilla Excel. TP final de la materia Introducción a la ingeniería de software asistida por IA (Maestría en IA). Demo Day: 14/10/2026.

Antes de cambiar el modelo de datos o las reglas de negocio, leé `docs/decisiones-arquitectura.md`. Cada decisión tiene un código (D01 a D30); citalo en specs, planes y commits cuando corresponda.

Lenguaje del dominio: cada médico tiene horarios pactados (día, hora de inicio, duración, frecuencia en semanas). Lo habitual es todas las semanas; algunos son semana por medio. Cada horario es de un solo médico. El coordinador es otro rol: no hace guardias.

## Stack

1. Backend: Python, FastAPI, SQLAlchemy, Alembic.
2. Base: Supabase (Postgres). RLS activado sin políticas; el backend se conecta con credenciales propias.
3. Autenticación: Supabase Auth con email y contraseña, y registro con código de coordinación (D06, D30). El backend verifica el token y vincula la cuenta con el Usuario. Nunca se guardan contraseñas en tablas propias.
4. Frontend: React con Vite, en `frontend/` con su `package.json`. Web responsive instalable (PWA). En producción, el backend sirve el resultado de la compilación como estáticos (un solo despliegue). El prototipo HTML existente es solo referencia visual: no se reutiliza su código.
5. Pruebas: pytest contra Postgres (nunca contra SQLite: el modelo usa índices parciales y restricciones de exclusión).

## Estructura

1. `backend/`: API, dominio, persistencia, migraciones, scripts (seed y reinicio de demo). Tiene su propio CLAUDE.md.
2. `frontend/`: interfaz. Tiene su propio CLAUDE.md.
3. `docs/decisiones-arquitectura.md`: decisiones del brainstorming.
4. `docs/superpowers/specs` y `docs/superpowers/plans`: specs y planes de cada funcionalidad.

## Reglas del dominio que nunca se rompen

1. El futuro normal se calcula desde la plantilla; un turno se guarda solo cuando se genera una vacante o cuando se consolida (D11).
2. Identidad del turno: horario pactado + fecha de inicio; en la API "horarioId:fecha" (D09).
3. Un turno ya materializado no se recalcula si cambia la plantilla (D11, D12).
4. El semáforo se calcula; no existe una columna de semáforo (D08).
5. Toda acción de dominio es una transacción que incluye su evento en la bitácora y sus notificaciones (D22).
6. La bitácora solo se agrega; nunca se edita ni se borra.
7. Los permisos se validan en el backend, aunque la interfaz oculte la acción.
8. La concurrencia se resuelve con restricciones de la base, no con lógica en memoria.
9. Nunca se borra un usuario (D24).
10. Toda hora se interpreta en America/Argentina/Buenos_Aires y se guarda con zona horaria. Toda lógica que dependa de "ahora" usa el reloj inyectable (D27), nunca la hora del sistema directamente.

## Diseño

Resumen del diseño; el detalle y las alternativas descartadas están en `docs/decisiones-arquitectura.md`.

Modelo de datos (modelo C5, D08):
1. Usuario: nombre, email, rol (MEDICO o COORDINADOR), estado (PENDIENTE, ACTIVO, BAJA), fecha de baja, identificador de Supabase Auth.
2. HorarioPactado: identidad estable de un horario semanal. VersionHorario: médico (vacío si el titular se dio de baja), día, hora de inicio, duración, frecuencia en semanas, fecha ancla, vigencia.
3. Turno: una guardia concreta, guardada solo cuando le pasa algo o cuando se consolida. Única por (horario, fecha). Guarda snapshot de inicio, fin y titular, el asignado actual y el realizador.
4. Vacante: aviso de ausencia sobre un turno; como máximo una abierta por turno; motivo visible solo para coordinadores.
5. Postulacion: oferta de un médico para cubrir un turno (no una vacante); única por (turno, médico).
6. EventoTurno: bitácora de acciones, solo de agregar.
7. Notificacion: aviso dentro de la app para un usuario.

Lo que se calcula y no se guarda: turnos futuros sin novedades, semáforo, etiqueta BAJA, orden de candidatos, horas sin cobertura.

Endpoints principales:
Todos los endpoints van bajo el prefijo `/api` (por ejemplo, `GET /api/turnos`); el OpenAPI queda en `/docs`.
1. Sesión: GET /me. Registro y login los maneja Supabase Auth; el código de coordinación se valida en POST /registro.
2. Calendario: GET /turnos?desde&hasta, GET /turnos/{turnoId} (detalle y línea de tiempo).
3. Vacantes y postulaciones: POST /turnos/{turnoId}/vacantes, POST /vacantes/lote, POST /vacantes/{id}/retiro, POST /turnos/{turnoId}/postulaciones, POST /postulaciones/{id}/retiro, GET /turnos/{turnoId}/candidatos. Cuerpos y respuestas en el OpenAPI de /docs (esquemas en `backend/app/api/esquemas_operacion.py`). Todas son reales (generar vacante, lote, retiro, postulación, candidatos y asignación).
4. Coordinación: PUT /turnos/{turnoId}/asignacion, POST /turnos/{turnoId}/sin-cobertura, POST /turnos/{turnoId}/rectificacion, POST /consolidacion, GET /indicadores/sin-cobertura.
5. Staff y plantilla (solo coordinadores): GET /usuarios, PATCH /usuarios/{id} (activar, cambiar rol), POST /usuarios/{id}/baja, GET /horarios, POST /horarios, POST /horarios/{id}/versiones (modificar o designar titular; devuelve los turnos afectados), POST /horarios/{id}/cierre. Las altas de usuarios son por registro (D30).
6. Notificaciones: GET /notificaciones, POST /notificaciones/{id}/leida.
7. Solo en modo demo: POST /demo/reloj.

Contrato entre interfaz y servidor:
1. JSON sobre HTTP; el contrato completo es el OpenAPI que genera FastAPI en /docs.
2. Token de Supabase Auth en el encabezado Authorization en todos los pedidos.
3. Identificador de turno compuesto "horarioId:fecha" (D09).
4. Errores con formato único: un código legible por la interfaz y un mensaje. 401 sin sesión, 403 rol insuficiente, 404 inexistente, 409 conflicto de estado o concurrencia, 422 regla de negocio.
5. JSON en camelCase (por ejemplo, `horarioId`, `duracionHoras`). Instantes en ISO 8601 con desplazamiento (`2026-10-17T08:00:00-03:00`).

## Forma de trabajo

1. Una branch por funcionalidad (feature/nombre-corto). Flujo de Superpowers para funcionalidades grandes; cambios chicos sin el flujo completo.
2. Commits chicos, en español, que describen el cambio.
3. Merge a main mediante pull request en GitHub. Cada pull request lo revisa otro integrante del equipo en GitHub (aprobación o comentarios) antes del merge, además de la revisión de código de Superpowers.
4. Antes de dar algo por terminado: correr las pruebas y, si tocaste la interfaz, verificarla con Playwright.
5. Si una tarea contradice una decisión de `docs/decisiones-arquitectura.md`, frená y preguntá en lugar de improvisar.
6. Los prompts principales de cada funcionalidad se registran en `docs/prompts-principales.md`. Los desvíos del agente, en `docs/bitacora-de-desvios.md`.

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
cd frontend && npm run build                                           # compilar el frontend (frontend/dist); si existe, el backend la sirve en /
docker build -t guardia-viva .                                         # imagen de producción (la que publica Render); ver docs/despliegue.md
```

El reinicio de la demo es el mismo script de datos de ejemplo; en F2 a F4 suma historia y vacantes.

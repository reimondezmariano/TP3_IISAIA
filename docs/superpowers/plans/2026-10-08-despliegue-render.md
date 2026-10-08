# Despliegue en Render con Supabase. Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** publicar Guardia Viva en Render (plan gratis) como un solo servicio web: FastAPI atiende `/api` y sirve también la compilación del frontend (D05), conectado a la base de Supabase y con redespliegue automático en cada merge a `main`.

**Arquitectura:** un `Dockerfile` en dos etapas compila el frontend con Node y arma la imagen de Python con la compilación adentro; `render.yaml` declara el servicio y las variables sin valores secretos. FastAPI monta `frontend/dist` en `/` después de las rutas de `/api`. Las migraciones de Supabase no corren en Render (el plan gratis no tiene comando previo al despliegue): se aplican desde tu computadora con Alembic apuntando a Supabase.

**Tecnologías:** Docker (Render), FastAPI `StaticFiles`, Vite, Alembic, Supabase (Postgres + Auth).

**Spec:** `docs/decisiones-arquitectura.md`, D02, D05, D06, D07 y D27; `docs/plan-de-implementacion.md` (F6, "despliegue con el backend sirviendo la compilación").

## Restricciones globales

- Ningún valor secreto en el repo: cadena de la base, código de coordinación, claves. En `render.yaml` van con `sync: false` y se cargan a mano en el panel de Render. La clave pública (anon) de Supabase y la URL del proyecto no son secretas, pero tampoco se versionan: se cargan en el panel igual que las demás.
- El servidor sirve el frontend solo si existe `frontend/dist`: en desarrollo y en las pruebas no cambia nada.
- `/api/...` que no existe responde 404 con el formato de error de la API, no la página del frontend.
- Pruebas siempre contra el Postgres local; ninguna prueba toca Supabase.
- Todo lo que corre contra Supabase lo ejecuta una persona del equipo y no un agente (migraciones, seed, paneles).
- Commits chicos, en español, con la decisión citada. Cada commit termina con la línea `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Un commit por tarea.

## Supuestos a confirmar

1. **Docker en Render** y no el entorno nativo de Python: la imagen necesita Node (compilar) y Python (servir) y Docker lo resuelve sin depender de qué traiga Render. Si el equipo prefiere el entorno nativo, cambian la tarea 2 y los comandos de la tarea 4.
2. **Variables de la interfaz en la compilación:** Vite las incrusta al compilar (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`). El `Dockerfile` las recibe como `ARG` y Render pasa las variables del servicio como argumentos de compilación. Hay que confirmarlo en el primer despliegue; si no llegaran, se pasan por `docker build --build-arg` desde el panel.
3. **Plan gratis:** el servicio se duerme tras unos 15 minutos sin tráfico y el primer pedido tarda hasta un minuto en despertarlo. Para la demo se abre la app unos minutos antes, o se configura un pedido periódico a `/api/health` desde un servicio externo gratuito. Los límites exactos se verifican en el panel de Render.
4. **MODO_DEMO=true** en Render durante la demo (D27: el reloj de demo y el reinicio). Se apaga al terminar.
5. **El seed no corre en Render:** se ejecuta desde tu computadora contra Supabase, con confirmación, y borra los datos actuales.

## Foco de revisión

1. **`/api/lo-que-sea` no debe devolver la página del frontend** (una ruta mal escrita de la interfaz parecería un 200). Prueba en la tarea 1.
2. **Archivos fuera de la compilación** (`/../.env`, `/assets/../../backend/.env`): el servidor no puede servir nada fuera de `frontend/dist`. Prueba en la tarea 1.
3. **Sin `frontend/dist`** (desarrollo y CI): la app arranca igual y `/` responde 404. Prueba en la tarea 1.
4. **La imagen no puede llevar secretos ni el `.env` local:** `.dockerignore` los excluye. Verificación en la tarea 2.
5. **Migrar la base equivocada:** antes de `alembic upgrade head`, mostrar a qué base apunta y la versión actual. Paso explícito en la guía de la tarea 4.

---

## Estructura de archivos

```
backend/app/main.py            (T1)  monta frontend/dist si existe
backend/tests/test_frontend_estatico.py   (T1)
Dockerfile, .dockerignore      (T2)  raíz del repo
render.yaml                    (T3)  raíz del repo
docs/despliegue.md             (T4)  guía paso a paso en lenguaje simple
CLAUDE.md, backend/CLAUDE.md   (T4)  comandos y variables
```

---

### Task 1: FastAPI sirve la compilación del frontend

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_frontend_estatico.py`

**Interfaces:**
- Produces: `crear_app(carpeta_frontend: Path | None = None) -> FastAPI`. Sin argumento usa `<raíz del repo>/frontend/dist`. Si la carpeta existe, monta `StaticFiles(directory=..., html=True)` en `/` después de incluir el router de `/api`; si no existe, no monta nada.

- [ ] **Step 1: Escribir las pruebas que fallan** con una carpeta temporal (`tmp_path`) que tiene `index.html` ("<h1>Guardia Viva</h1>") y `assets/app.js`: `test_la_raiz_sirve_el_index`, `test_sirve_un_archivo_de_assets_con_su_tipo`, `test_api_health_sigue_respondiendo_json` (GET `/api/health`), `test_una_ruta_de_api_inexistente_responde_404_y_no_el_index` (GET `/api/no-existe`: status 404 y el cuerpo no contiene "Guardia Viva"), `test_no_sirve_archivos_fuera_de_la_carpeta` (GET `/..%2Fsecreto.txt` y `/assets/..%2F..%2Fsecreto.txt` con un `secreto.txt` junto a la carpeta: nunca 200 con su contenido), `test_sin_carpeta_la_app_arranca_y_la_raiz_responde_404`. Las pruebas no necesitan Postgres.
- [ ] **Step 2: Correr y verificar que fallan:** `python -m pytest tests/test_frontend_estatico.py -v` → FAIL.
- [ ] **Step 3: Implementar** el parámetro y el montaje en `crear_app`; `app = crear_app()` queda igual.
- [ ] **Step 4: Correr y verificar que pasan,** y la suite completa `python -m pytest -q` → PASS.
- [ ] **Step 5: Commit** `git commit -m "FastAPI sirve la compilación del frontend si existe (D05)"`.

### Task 2: Imagen de Docker

**Files:**
- Create: `Dockerfile`, `.dockerignore`

**Interfaces:**
- Produces: imagen que, al arrancar, ejecuta `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` desde `backend/`, con `frontend/dist` en su lugar. Etapa 1 (Node): `npm ci` y `npm run build` en `frontend/`, con `ARG VITE_SUPABASE_URL` y `ARG VITE_SUPABASE_ANON_KEY`. Etapa 2 (Python 3.12): instala el backend (`pip install .` desde `backend/`), copia la compilación y corre con un usuario sin privilegios.
- `.dockerignore` excluye: `.git`, `**/.env`, `**/.venv`, `**/node_modules`, `**/__pycache__`, `frontend/dist`, `frontend/test-results`, `backend/tests` y `docs`.

- [ ] **Step 1: Escribir el Dockerfile y el .dockerignore.**
- [ ] **Step 2: Compilar la imagen** con valores de prueba inventados para los `ARG`: `docker build -t guardia-viva:prueba --build-arg VITE_SUPABASE_URL=https://ejemplo.supabase.co --build-arg VITE_SUPABASE_ANON_KEY=clave-de-prueba .` → termina sin errores.
- [ ] **Step 3: Verificar que no lleva secretos:** `docker run --rm guardia-viva:prueba sh -c "ls -a /app /app/backend | grep -E '^\.env$' || echo sin-env"` → imprime `sin-env`.
- [ ] **Step 4: Arrancar contra el Postgres local** (`DATABASE_URL` al contenedor de docker-compose, con `--add-host` o red compartida) y probar `GET /api/health` y `GET /` → 200 y la página del frontend.
- [ ] **Step 5: Commit** `git commit -m "Dockerfile en dos etapas para publicar backend y frontend en un solo servicio"`.

### Task 3: Configuración de Render

**Files:**
- Create: `render.yaml`

**Interfaces:**
- Produces: un servicio web `guardia-viva`, `runtime: docker`, `plan: free`, `healthCheckPath: /api/health`, `autoDeploy: true` sobre `main`. Variables, todas cargadas en el panel y marcadas `sync: false` salvo las fijas: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET` (opcional), `CODIGO_COORDINACION`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (secretas o específicas del proyecto); fijas: `APP_TIMEZONE=America/Argentina/Buenos_Aires` y `MODO_DEMO=true`.

- [ ] **Step 1: Escribir `render.yaml`.**
- [ ] **Step 2: Validar el YAML** (`python -c "import yaml,sys; yaml.safe_load(open('render.yaml'))"`) y revisar que ningún valor secreto esté escrito en el archivo (`grep -nE "postgres(ql)?://|eyJ|[A-Z0-9]{5}-[A-Z0-9]{5}" render.yaml` no devuelve nada).
- [ ] **Step 3: Commit** `git commit -m "Configuración de Render: un servicio web con redespliegue en cada merge a main"`.

### Task 4: Guía de despliegue y documentación

**Files:**
- Create: `docs/despliegue.md`
- Modify: `CLAUDE.md` (sección Comandos), `backend/CLAUDE.md` (convención nueva), `docs/prompts-principales.md`

La guía está escrita para alguien que nunca usó Render, con estas secciones y orden:

1. **Qué es cada pieza:** Supabase guarda los datos y las cuentas; Render es la computadora en internet donde corre la app.
2. **Supabase (una sola vez), en el panel:** (a) Authentication, Sign In / Providers, Email: apagar "Confirm email" y guardar (D06). (b) Authentication, URL Configuration: poner la dirección de Render en "Site URL" cuando se conozca. (c) Project Settings, API: copiar la URL del proyecto y la clave pública (anon). (d) Project Settings, Database: copiar la cadena del Session pooler.
3. **Migraciones desde tu computadora, con cuidado:** (a) Poner la cadena de Supabase en `DATABASE_URL` de `backend/.env` (el archivo no se sube a git). (b) Mostrar a qué base apunta y en qué versión está: `cd backend && .venv/Scripts/alembic current` → debe decir `0001`. (c) Aplicar: `.venv/Scripts/alembic upgrade head` → debe terminar en la última versión pendiente (hoy `0004`). (d) Volver `DATABASE_URL` a la base local si se va a trabajar con ella. **Se hace una sola vez, al final:** cuando estén mergeados la etapa 3 de F3 y todo lo demás que cambie el esquema, y no antes. Así Supabase recibe todas las migraciones pendientes de una vez (hoy 0002, 0003 y 0004; si la etapa 3 o el semáforo agregan alguna, también esa) y no queda a medio migrar.
4. **Datos de ejemplo:** `.venv/Scripts/python -m scripts.seed --confirmar` apuntando a Supabase. Advertencia en negrita: borra los datos que haya.
5. **Render, en el panel:** New, Blueprint, elegir el repositorio y la rama `main`; Render lee `render.yaml`. Cargar a mano las variables de la lista de la tarea 3 (de dónde sale cada una). Esperar el primer despliegue (varios minutos) y abrir la dirección `https://guardia-viva-….onrender.com`.
6. **Después de desplegar:** poner esa dirección en "Site URL" de Supabase; probar registro, login y calendario; cómo reiniciar la demo; cómo despertar el servicio antes de presentar.
7. **Si algo falla:** logs de Render, la pantalla en blanco (suele ser una variable `VITE_` sin cargar: se corrige y se vuelve a desplegar, porque la compilación las incrusta), error 401 o 503 de autenticación (falta `SUPABASE_URL`), y cómo volver al despliegue anterior.
8. **Qué NO hacer:** pegar claves en el chat o en archivos del repo; apuntar las pruebas a Supabase.

- [ ] **Step 1: Escribir la guía** con esas secciones y los nombres exactos de menús y variables.
- [ ] **Step 2: Actualizar `CLAUDE.md` y `backend/CLAUDE.md`** (comando de compilación local `cd frontend && npm run build` y el servicio estático; convención de que el servidor sirve `frontend/dist` solo si existe) y registrar el prompt en `docs/prompts-principales.md`.
- [ ] **Step 3: Verificar que la guía no contiene valores reales:** el mismo `grep` de secretos de la tarea 3 sobre `docs/despliegue.md` no devuelve nada.
- [ ] **Step 4: Commit** `git commit -m "Guía de despliegue en Render y Supabase, en lenguaje simple"`; pushear y abrir el PR.

---

## Lo que tenés que hacer vos (resumen en lenguaje simple)

Nada de esto lo hace el agente. El código de las tareas 1 a 4 se puede mergear antes, pero lo que toca Supabase (los puntos 1 y 2) se hace recién cuando estén mergeados la etapa 3 y todo lo demás que cambie el esquema, una sola vez:

1. **En Supabase:** apagar "Confirm email" y guardar; anotar la URL del proyecto, la clave pública (anon) y la cadena del Session pooler.
2. **En tu computadora:** poner la cadena del Session pooler en `backend/.env`, correr dos comandos de Alembic (ver cuál es la versión actual antes de migrar) y, solo si querés los datos de ejemplo, el seed. Yo te dejo los comandos exactos en la guía.
3. **En Render:** crear una cuenta, conectar GitHub con permiso solo a este repositorio, crear un Blueprint desde `main` y pegar las variables que te listo (seis, más dos fijas).
4. **Después:** copiar la dirección que te da Render a Supabase ("Site URL") y probar el registro y el login desde el celular.

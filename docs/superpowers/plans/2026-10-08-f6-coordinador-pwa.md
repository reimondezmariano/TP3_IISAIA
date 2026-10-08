# F6 Coordinador y PWA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans para implementar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`).

**Goal:** App instalable (PWA), postulaciones reales del médico y panel de cobertura del coordinador (candidatos por equidad, asignación, sin cobertura, horas sin cobertura del mes).

**Architecture:** Todo pasa por `lib/api.js`. Un módulo por área (`lib/postulaciones.js`, `lib/cobertura.js`) con su hook; los componentes solo presentan. Se elimina `src/simulado/` (ya no queda nada simulado). No se toca `backend/`.

**Tech Stack:** React 19, Vite, Vitest + Testing Library, Playwright, service worker sin librerías.

**Spec:** sin spec propio; contrato = OpenAPI de `/docs` y `backend/app/api/esquemas_operacion.py`; decisiones D15 a D19, D24, D27 de `docs/decisiones-arquitectura.md`.

## Global Constraints

- No tocar `backend/`.
- Errores `{codigo, mensaje}`: la interfaz decide por `codigo` y muestra `mensaje`. JSON en camelCase.
- Horas en America/Argentina/Buenos_Aires; "hoy" sale de `GET /api/health` (D27).
- Permisos validados en el backend; la interfaz solo oculta (regla 7).
- El orden de candidatos lo da el servidor (D17); las horas de la semana se muestran como dato, no ordenan.
- Un commit por tarea, en español.

## Hallazgos que condicionan el plan

1. Los endpoints de postulaciones, candidatos, asignación, sin cobertura e indicadores son reales en `main`.
2. (Resuelto al traer main, ver Task 5) `GET /api/turnos` no informaba la vacante abierta (la rama `feature/turnos-con-vacante` de Mariano la agrega y no está mergeada). Consecuencias:
   - No se puede mostrar qué turnos ajenos tienen vacante ni armar una lista de vacantes abiertas sin inventar datos. El médico ve "Postularme" en cualquier guardia futura ajena y el servidor decide (`TURNO_SIN_VACANTE`); el coordinador abre el panel de cobertura desde el calendario.
   - El id de la postulación solo lo devuelve el POST: se recuerda en `localStorage` (por usuario), igual que ya se hacía con las vacantes propias. Pendiente de Mariano junto con el id de vacante.
3. Tarea 5 del pedido (retirar usando el dato del servidor y borrar `localStorage`) queda pendiente de Mariano.

## Review Focus

- Postularse a un turno sin vacante / ya empezado / ya postulado: se muestra el mensaje del servidor y no se recuerda nada.
- Retirar una postulación ya retirada (409) o inexistente (404): se olvida y se muestra el mensaje.
- Asignar a alguien cuando el turno ya tiene asignado (409 `YA_TIENE_ASIGNADO`): se ofrece reasignar de forma explícita.
- Candidatos no elegibles: se listan con su motivo, sin botón de elegir.
- Service worker: nunca cachea `/api/*`; si no hay red, el shell abre igual.
- `localStorage` bloqueado o roto: todo funciona igual.

---

### Task 1: PWA (manifest, ícono, service worker)
**Files:** Create `frontend/public/manifest.webmanifest`, `frontend/public/sw.js`, `frontend/public/icono-192.png`, `icono-512.png`, `icono-maskable-512.png`, `frontend/src/lib/pwa.js`, `frontend/src/lib/pwa.test.js`; Modify `frontend/index.html`, `frontend/src/main.jsx`, `frontend/e2e/operativo.spec.js` (o nuevo `pwa.spec.js`).

- [ ] Prueba que falla: `registrarServiceWorker({ navegador, produccion })` registra `/sw.js` solo si hay `serviceWorker` y es producción; no tira si el registro falla.
- [ ] Implementar `pwa.js`, íconos (generados con Pillow), manifest (`name`, `short_name`, `start_url: "/"`, `display: standalone`, `theme_color #1f5f8b`, íconos), `sw.js` (precache del shell; navegaciones red-primero con caída al shell; assets cache-primero; ignora todo lo que no sea GET same-origin y `/api/`).
- [ ] `index.html`: `<link rel="manifest">`, `apple-touch-icon`. `main.jsx`: registrar en producción.
- [ ] Prueba e2e: la página enlaza un manifest válido con íconos.
- [ ] `npm test`, `npm run build`, commit.

### Task 2: Médico se postula y retira la postulación
**Files:** Create `frontend/src/lib/postulaciones.js` (+test), `frontend/src/lib/estadoTurno.js` (+test), `frontend/src/pantallas/usePostulaciones.js` (+test); Modify `Calendario.jsx`, `DetalleTurno.jsx` (+test); Delete `frontend/src/simulado/`.

**Interfaces:**
- `postular(api, turnoId)` → `POST /api/turnos/{id}/postulaciones` → `{id, turnoId, medico, creadaEn, retiradaEn}`
- `retirarPostulacion(api, postulacionId)` → `POST /api/postulaciones/{id}/retiro`
- `leerRecordadas(usuarioId)`, `recordar`, `olvidar` con clave `guardia-viva:postulaciones:{usuarioId}`
- `estadoDe({turno, usuario, ahora, vacanteAbierta, postulado})` → `{tipo, etiqueta, urgente, postulado, acciones}`; sin postulantes inventados.
- `usePostulaciones(api, usuario)` → `{postuladas, postular(turnoId), retirar(turnoId)}`

- [ ] Pruebas que fallan para cada módulo (estado: PASADO, mío, BAJA, vacante propia, ajeno futuro → `POSTULARME`, ya postulado → `RETIRAR_POSTULACION`, coordinador sin acciones de médico).
- [ ] Implementar; quitar el rótulo "Simulado" y el hash; conectar el detalle.
- [ ] Prueba e2e: postularse y retirar contra la API simulada, y error `TURNO_SIN_VACANTE`.
- [ ] `npm test`, commit.

### Task 3: Coordinador: cobertura de un turno
**Files:** Create `frontend/src/lib/cobertura.js` (+test), `frontend/src/coordinacion/useCobertura.js`, `frontend/src/coordinacion/PanelCobertura.jsx` (+test); Modify `DetalleTurno.jsx`, `Calendario.jsx`, `estilos.css`, e2e.

**Interfaces:**
- `candidatosDe(api, turnoId)` → `GET /api/turnos/{id}/candidatos` → `{turnoId, mes, candidatos[]}`
- `asignar(api, turnoId, medicoId, reasignar)` → `PUT /api/turnos/{id}/asignacion`
- `marcarSinCobertura(api, turnoId)` → `POST /api/turnos/{id}/sin-cobertura`

- [ ] Pruebas que fallan: lista en el orden del servidor mostrando coberturas del mes y horas de la semana (como dato); no elegibles con motivo y sin botón; elegir llama a `asignar`; asignar directo con un médico activo elegido de `GET /api/usuarios`; `YA_TIENE_ASIGNADO` ofrece "Reasignar"; sin cobertura muestra el error del servidor si no empezó.
- [ ] Implementar el panel y montarlo en el detalle cuando `usuario.rol === "COORDINADOR"`.
- [ ] e2e con API simulada, commit.

### Task 4: Indicador de horas sin cobertura del mes
**Files:** Create `frontend/src/coordinacion/IndicadorSinCobertura.jsx` (+test); Modify `Calendario.jsx`.

- [ ] Prueba: con `GET /api/indicadores/sin-cobertura?desde=AAAA-MM&hasta=AAAA-MM` → `[{mes, horas, turnos}]` muestra "X h sin cobertura en el mes (N turnos)"; error del servidor no rompe el calendario.
- [ ] Implementar (solo coordinadores; el mes sale de `ahora`), commit.

### Task 5: Vacante abierta de `GET /api/turnos` y acciones por rol
Se trajo main (rama `feature/turnos-con-vacante`): `turno.vacante` es `null` o `{id, urgente, generadaPor}`.

- [x] Retirar con `turno.vacante.id`; se elimina el `localStorage` de vacantes; `estadoTurno` usa `vacante` y `urgente` del servidor.
- [x] Acciones por rol en el detalle: médico titular (avisar ausencia, retirar aviso si la generó), coordinador (generar y retirar vacante, panel de cobertura).
- [x] Tras cada acción se recarga la semana (`refrescar`); las pruebas de turnos suman la clave `vacante`.
- Limitación: el turno no informa al asignado, así que "asignado" no puede avisar ausencia desde la interfaz (el servidor sí lo permite).

### Cierre
- [ ] Revisión de toda la branch, traer main, Vitest y Playwright, push y pull request (sin mergear). Prompts y desvíos van en la descripción del PR (no se editan `docs/prompts-principales.md` ni `docs/bitacora-de-desvios.md`).

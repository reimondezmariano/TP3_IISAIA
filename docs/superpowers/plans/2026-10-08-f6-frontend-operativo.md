# F6 Frontend operativo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans para implementar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`).

**Goal:** Conectar el frontend a los endpoints reales de vacantes, staff y notificaciones, y corregir el nombre vacío en "Completá tu registro".

**Architecture:** Todo pasa por `lib/api.js` (se le suma `patch`). Cada área tiene su hook que habla con la API y su pantalla o componente de presentación. Las postulaciones siguen simuladas (`src/simulado/`): no son parte de esta fase. No se toca `backend/`.

**Tech Stack:** React 19, Vite, Vitest + Testing Library, Playwright.

**Spec:** no hay spec propio; el contrato es el OpenAPI de `/docs`, `backend/CLAUDE.md` y las decisiones D05, D15, D24, D26, D30, D32 de `docs/decisiones-arquitectura.md`.

## Global Constraints

- No tocar `backend/`.
- Errores `{codigo, mensaje}`: la interfaz decide por `codigo` y muestra `mensaje`. JSON en camelCase.
- Toda hora se muestra en America/Argentina/Buenos_Aires; "hoy" sale de `GET /api/health` (D27), no del navegador.
- Los permisos los valida el backend; la interfaz solo oculta (regla 7). Pantalla de staff visible solo para `rol === "COORDINADOR"`.
- Un commit por tarea, en español.

## Desvíos respecto del pedido (se registran en `docs/bitacora-de-desvios.md`)

1. `POST /api/vacantes/lote` es solo de coordinadores (`requiere_coordinador`). Para un médico con varias fechas la interfaz llama a `POST /api/turnos/{id}/vacantes` una vez por fecha, no es todo o nada, y muestra qué fechas quedaron y cuáles fallaron. `lote` queda en `lib/vacantes.js` y se usa si el usuario es coordinador.
2. El servidor no informa qué vacantes están abiertas (`GET /turnos` no las trae y `GET /turnos/{id}` no existe). Para poder retirar, la interfaz recuerda en el navegador (`localStorage`, por usuario) las vacantes que generó. Si el servidor responde que ya no está abierta, se olvida. En otro dispositivo no aparece el botón de retirar.

## Review Focus

- Retirar una vacante que ya no está abierta (409 `VACANTE_NO_ABIERTA`) o que no existe (404): se olvida y se muestra el mensaje.
- Avisar de nuevo un turno con vacante abierta (409 `VACANTE_YA_ABIERTA`) en una lista de varias fechas: las demás siguen.
- `localStorage` bloqueado o con contenido roto: la pantalla funciona igual.
- Consulta de notificaciones que falla (red caída o 401): no rompe la pantalla ni repite avisos emergentes.
- Una notificación urgente ya leída o ya mostrada no vuelve a mostrarse como aviso emergente.
- Nombre sugerido ausente en el registro: el campo queda vacío y editable.

---

### Task 1: `patch` en el cliente HTTP
**Files:** Modify `frontend/src/lib/api.js`, `frontend/src/lib/api.test.js`

- [ ] Prueba que falla: `patch("/api/usuarios/3", {rol:"COORDINADOR"})` manda método PATCH con cuerpo JSON y Bearer.
- [ ] Agregar `patch: (ruta, cuerpo) => pedir("PATCH", ruta, { cuerpo })`.
- [ ] `npm test`, commit "Cliente HTTP: método PATCH".

### Task 2: Nombre sugerido en "Completá tu registro"
**Files:** Modify `SesionProvider.jsx`, `CompletarRegistro.jsx`, `SesionProvider.test.jsx`; Create `CompletarRegistro.test.jsx`

El nombre se perdía: `signUp` lo guarda en `user_metadata.nombre`, pero si `POST /registro` falla el formulario arrancaba vacío. `SesionProvider` expone `nombreSugerido` (de `session.user.user_metadata.nombre`, vacío si no hay) y `CompletarRegistro` lo usa como valor inicial.

- [ ] Pruebas: con `user_metadata.nombre = "Ana Gómez"` el campo Nombre arranca con ese valor y se puede editar; sin metadata queda vacío.
- [ ] Implementar y commit "Completá tu registro: el nombre ya cargado en la cuenta llena el campo".

### Task 3: Avisar ausencia y retirarla contra la API real
**Files:** Create `src/lib/vacantes.js` (+test), `src/pantallas/useAusencias.js` (+test), `src/componentes/AusenciaVarios.jsx` (+test); Modify `Calendario.jsx`, `DetalleTurno.jsx`(+test), `src/simulado/*` (se saca lo de vacantes propias)

`lib/vacantes.js`: `generarVacante(api, turnoId, motivo)` → `POST /api/turnos/{id}/vacantes {motivo}`; `generarLote(api, turnoIds, motivo)` → `POST /api/vacantes/lote {turnoIds, motivo}`; `retirarVacante(api, id)` → `POST /api/vacantes/{id}/retiro`; `leerRecordadas(usuarioId)` / `recordar(usuarioId, turnoId, vacanteId)` / `olvidar(usuarioId, turnoId)` sobre `localStorage` con try/catch.
`useAusencias(api, usuario)`: estado `abiertas` (turnoId → vacanteId); `avisar(turnoId, motivo)`, `avisarVarios(turnoIds, motivo)` (coordinador: lote; médico: de a una, devuelve `{ok, fallaron:[{turnoId, mensaje}]}`), `retirar(turnoId)`.
`AusenciaVarios`: botón "Avisar varias fechas" en el calendario del médico; elige desde/hasta (máx. 62 días), carga `GET /api/turnos` del rango, lista con casillas sus turnos futuros (`titular.id === usuario.id`, que no terminaron), motivo, enviar.
`DetalleTurno`: quita el rótulo "Simulado" de la vacante propia; los botones llaman a la API, deshabilitados mientras envían, con el error visible.

- [ ] Pruebas de `lib/vacantes.js` (rutas, cuerpos, localStorage roto no tira).
- [ ] Pruebas de `useAusencias` (avisar guarda id; retirar llama y olvida; 409 `VACANTE_NO_ABIERTA` olvida y devuelve el error; varios: una falla y las demás siguen).
- [ ] Pruebas de `AusenciaVarios` y `DetalleTurno`.
- [ ] Implementar. Commit "Médico: avisar ausencia de una o varias fechas y retirarla contra la API".

### Task 4: Notificaciones (campanita, sondeo, aviso emergente)
**Files:** Create `src/notificaciones/useNotificaciones.js` (+test), `Campanita.jsx` (+test), `AvisoUrgente.jsx` (+test); Modify `estilos.css`, `Calendario.jsx` (cabecera)

`useNotificaciones(api, {intervaloMs = 12000})`: `GET /api/notificaciones` al montar y cada 12 s (dentro de 10 a 15 s); expone `lista`, `noLeidas`, `marcarLeida(id)` (`POST /api/notificaciones/{id}/leida`), `marcarTodas`, `urgentesNuevas` (tipo `VACANTE_URGENTE`, no leídas, no mostradas antes en esta sesión), `descartarUrgente(id)`. Un fallo de red conserva la lista anterior y reintenta en el siguiente ciclo. Se detiene al desmontar.
`Campanita`: botón con contador de no leídas y panel con la lista (mensaje, hora local), "Marcar leída" y "Marcar todas".
`AvisoUrgente`: `role="alert"` emergente con el mensaje de la vacante urgente (D05, D15) y botón "Entendido" que la marca como leída.

- [ ] Pruebas con temporizadores falsos: sondea cada 12 s, para al desmontar, conserva la lista si falla, no repite la urgente.
- [ ] Implementar. Commit "Notificaciones: campanita, consulta periódica y aviso para vacantes urgentes".

### Task 5: Pantalla de staff (solo coordinadores)
**Files:** Create `src/staff/` con `useStaff.js`, `PantallaStaff.jsx`, `FilaUsuario.jsx`, `FormularioHorario.jsx`, `DesignarTitular.jsx`, `TurnosAfectados.jsx` y sus pruebas; Modify `App.jsx` / `Calendario.jsx` (navegación Calendario | Staff solo si `rol === "COORDINADOR"`), `estilos.css`

Endpoints: `GET /api/usuarios`, `PATCH /api/usuarios/{id}` (`{estado:"ACTIVO"}`, `{rol}`), `POST /api/usuarios/{id}/baja {fechaBaja}`, `GET /api/horarios`, `POST /api/horarios`, `POST /api/horarios/{id}/versiones`, `POST /api/horarios/{id}/cierre`.
- Lista: nombre, email, rol, estado (con fecha de baja), horarios (día, hora, duración, frecuencia). Pendientes con "Activar". "Cambiar rol" con confirmación. "Dar de baja" pide la fecha del último día activo (por defecto hoy del servidor).
- Horarios: formulario de alta (médico activo, día 1-7, hora, duración, frecuencia, vigente desde) y de modificación (versión desde una fecha; solo se mandan los campos cambiados). Después de cada cambio se muestran `turnosAfectados` (y `coberturasReabiertas` en la baja).
- Horarios en BAJA (`estado` del horario sin titular): sección "Horarios sin titular" con "Designar titular" (médico activo + fecha desde) → versión con `medicoId`.
- Códigos de error del servidor se muestran con su `mensaje`.

- [ ] Pruebas por componente con `api` falsa.
- [ ] Implementar. Commit "Pantalla de staff para coordinadores contra la API real".

### Task 6: e2e, documentación, revisión y pull request
**Files:** Modify `frontend/e2e/ayudas.js` (rutas simuladas nuevas), create `frontend/e2e/operativo.spec.js`, `frontend/CLAUDE.md`, `docs/prompts-principales.md`, `docs/bitacora-de-desvios.md`

- [ ] Playwright: médico avisa y retira; coordinador ve staff, activa un pendiente; campanita muestra no leídas y el aviso emergente.
- [ ] Actualizar `frontend/CLAUDE.md` (estructura nueva, simulado solo postulaciones) y los dos documentos de registro.
- [ ] Revisión de toda la branch (`superpowers:requesting-code-review`), corregir lo importante, traer main, correr Vitest y Playwright, subir la branch y abrir el pull request sin mergear.

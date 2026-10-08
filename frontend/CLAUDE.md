# Frontend de Guardia Viva

React + Vite, en JavaScript. Experiencia del médico (F4): login y registro con Supabase Auth, calendario semanal. F6: avisar ausencia y retirarla, postularse y retirar la postulación, notificaciones, pantalla de staff y app instalable (PWA), contra la API real. El prototipo HTML de la raíz (`index.html`) es solo referencia visual y no se reutiliza su código.

## Estructura

1. `src/lib/`: `api.js` (único cliente HTTP, manda `Authorization: Bearer`), `fechas.js` (semana y horas en Buenos Aires), `supabase.js` (solo para el login), `errores-auth.js`.
2. `src/sesion/`: `SesionProvider` reúne la sesión de Supabase y `GET /api/me` en un estado (`cargando`, `anonimo`, `sin-registro`, `pendiente`, `baja`, `activo`, `error`); `App.jsx` elige la pantalla según ese estado.
3. `src/pantallas/` y `src/componentes/`: interfaz. `Principal.jsx` es la pantalla de una cuenta activa (campanita, aviso emergente y, solo para coordinadores, la pestaña Staff).
4. `src/lib/vacantes.js` y `src/pantallas/useAusencias.js`: vacantes reales (`POST /turnos/{id}/vacantes`, retiro). `GET /turnos` trae `vacante` en cada turno (`null` o `{id, urgente, generadaPor}`, sin motivo: D25) y con ese id se retira (`POST /vacantes/{id}/retiro`); no se guarda nada en el navegador. Tras cada acción el calendario se recarga (`refrescar`). `POST /vacantes/lote` es solo de coordinadores: el médico con varias fechas llama a la ruta de una vacante por fecha (no es todo o nada) y se le informa cuáles fallaron.
5. `src/notificaciones/`: `useNotificaciones` consulta `GET /notificaciones` cada 12 s; `Campanita` y `AvisoUrgente` (vacantes urgentes, D05, D15).
6. `src/staff/`: pantalla de staff (D26): personas, horarios y designar titular en los horarios BAJA; muestra los turnos afectados que devuelve el servidor.
7. `src/lib/postulaciones.js` y `src/pantallas/usePostulaciones.js`: postularse y retirar la postulación (`POST /turnos/{id}/postulaciones`, `POST /postulaciones/{id}/retiro`). El médico ve "Postularme" solo en turnos ajenos con vacante abierta (o BAJA) que no empezaron. El id de la postulación solo lo devuelve el POST: se recuerda en `localStorage` por usuario (`lib/recuerdo.js`) hasta que `GET /turnos` la informe. `lib/estadoTurno.js` deriva etiqueta, urgencia y acciones según el rol: médico titular (avisar ausencia, retirar aviso si la generó él) y coordinador (generar y retirar vacante, más el panel de cobertura).
8. `src/coordinacion/`: `PanelCobertura` (candidatos por equidad D17 con horas de la semana como dato, elegir, asignar directo, reasignar, sin cobertura) e `IndicadorSinCobertura` (horas del mes). Sus estilos están en `coordinacion.css`.
9. PWA: `public/manifest.webmanifest`, íconos y `public/sw.js` (guarda el shell, nunca `/api/`); `lib/pwa.js` lo registra solo en producción.

## Convenciones

1. Toda llamada al servidor va a `/api/...` y pasa por `lib/api.js`, que manda el token de Supabase. En desarrollo, Vite la redirige a `http://localhost:8000`; en producción, el backend sirve la compilación (F6).
2. Los errores del servidor llegan como `{"codigo", "mensaje"}`: la interfaz decide por `codigo` y muestra `mensaje`. 401 `TOKEN_VENCIDO`/`TOKEN_INVALIDO`/`SIN_SESION` cierra la sesión.
3. El JSON viene en camelCase.
4. Las horas se muestran en America/Argentina/Buenos_Aires y la semana empieza el lunes. "Hoy" sale de `GET /api/health` (`ahora`, reloj del servidor, D27), no del navegador.
5. Variables públicas en `frontend/.env`: `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY`. El código de coordinación no se guarda en el frontend (D30).
6. Pruebas unitarias y de componentes con Vitest (el `auth` de Supabase se inyecta, `src/pruebas/auth-falso.js`); e2e con Playwright (Supabase y API simulados con `page.route`, más `e2e/contrato.spec.js` contra el backend real).

## Comandos (desde frontend/)

```bash
npm install && npx playwright install chromium   # una vez
npm run dev                                      # http://localhost:5173 (necesita el backend en el puerto 8000)
npm test                                         # Vitest
npm run build                                    # compila en dist/
npm run test:e2e                                 # Playwright; levanta backend y frontend si no están corriendo
```

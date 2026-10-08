# Frontend de Guardia Viva

React + Vite, en JavaScript. Experiencia del médico (F4): login y registro con Supabase Auth, calendario semanal. El prototipo HTML de la raíz (`index.html`) es solo referencia visual y no se reutiliza su código.

## Estructura

1. `src/lib/`: `api.js` (único cliente HTTP, manda `Authorization: Bearer`), `fechas.js` (semana y horas en Buenos Aires), `supabase.js` (solo para el login), `errores-auth.js`.
2. `src/sesion/`: `SesionProvider` reúne la sesión de Supabase y `GET /api/me` en un estado (`cargando`, `anonimo`, `sin-registro`, `pendiente`, `baja`, `activo`, `error`); `App.jsx` elige la pantalla según ese estado.
3. `src/pantallas/` y `src/componentes/`: interfaz. `src/simulado/`: datos simulados de vacantes y postulaciones; se reemplaza por la API cuando existan los endpoints.

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

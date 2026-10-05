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

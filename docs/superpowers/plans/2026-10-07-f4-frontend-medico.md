# F4: frontend del médico. Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** que un médico pueda registrarse, ingresar y ver su calendario semanal de guardias en React: pantalla de login y registro (con código de coordinación opcional) sobre Supabase Auth, aviso "esperando activación" para cuentas PENDIENTE, y calendario semanal que consume `GET /api/turnos`, con los botones de vacantes y postulaciones preparados sobre datos simulados.

**Arquitectura:** el token de Supabase Auth se obtiene siempre de la sesión de `supabase-js` y un único cliente HTTP (`lib/api.js`) lo manda en `Authorization: Bearer` en todas las llamadas. Un `SesionProvider` reúne sesión de Supabase y `GET /api/me` en una máquina de estados (`cargando`, `anonimo`, `sin-registro`, `pendiente`, `baja`, `activo`, `error`); `App` elige la pantalla según ese estado. El calendario pide la semana (lunes a domingo) y agrupa los turnos por día. Mientras no existan los endpoints de vacantes y postulaciones, `src/simulado/` deriva el estado de cada turno con una función pura y guarda las acciones del usuario en memoria; todo lo simulado se señala en la interfaz y vive en una sola carpeta para reemplazarlo después. Nada en `backend/` se modifica.

**Tecnologías:** React 19, Vite 7, `@supabase/supabase-js`, Vitest + Testing Library + jsdom (pruebas unitarias y de componentes), Playwright (e2e con Supabase y API simulados por `page.route`, más un contrato contra el backend real).

**Spec:** no hay spec propio: el plan se apoya en `docs/decisiones-arquitectura.md` (D05, D06, D13, D15, D16, D24, D25, D30), en `backend/CLAUDE.md`, en `frontend/CLAUDE.md` y en el pedido del 7/10/2026 (su texto se registra en la descripción del pull request). Las elecciones que quedan abiertas están en "Decisiones de este plan".

**Ejecución (definida por el equipo el 7/10/2026):** en la misma sesión, con superpowers:executing-plans (modo Native), tarea por tarea. Branch `feature/f4-frontend-medico` (ya creada), un commit por tarea. Al terminar, `npm test`, `npm run test:e2e`, verificación manual con Playwright del flujo de verdad contra el backend y revisión de código de la branch antes del pull request.

## Restricciones globales

- No se toca nada en `backend/`. Si algo del contrato no alcanza, se anota en la sección "Desvíos" de la descripción del pull request y se avisa; no se resuelve en el backend.
- Alcance de escritura: solo `frontend/` (incluido `frontend/CLAUDE.md`) y este plan. No se modifican `CLAUDE.md` de la raíz, `docs/prompts-principales.md` ni `docs/bitacora-de-desvios.md`: los prompts principales y los desvíos van en secciones propias de la descripción del pull request y Florencia los pasa a los documentos compartidos al final.
- Toda llamada a `/api/...` pasa por `lib/api.js` y manda `Authorization: Bearer <access_token de Supabase>`. Sin token no se hace el pedido: se falla con `SIN_SESION` (el backend respondería 401 `SIN_SESION`).
- Errores del servidor: `{"codigo", "mensaje"}`; la interfaz decide por `codigo` y muestra `mensaje` (`frontend/CLAUDE.md`).
- JSON en camelCase (`horarioId`, `duracionHoras`); instantes ISO 8601 con desplazamiento. Las horas se muestran en `America/Argentina/Buenos_Aires` (D13); la semana empieza el lunes. El turno pertenece a la fecha en que empieza (`turno.fecha`).
- El código de coordinación solo se escribe en el formulario y viaja a `POST /api/registro`; no se guarda en el frontend ni en el repositorio (D30). `frontend/.env` solo tiene valores públicos (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`) y no se versiona.
- Los permisos reales los valida el backend (regla 7): lo que la interfaz oculta es comodidad, no seguridad.
- Nunca se guardan contraseñas ni tokens a mano: la sesión la persiste `supabase-js`.
- Texto de la interfaz en español rioplatense (voseo), sin tecnicismos en los mensajes de error.
- Un commit por tarea, en español, citando decisiones. Cada commit termina con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Comandos desde `frontend/`. Antes de dar la funcionalidad por terminada: `npm test`, `npm run test:e2e` y verificación con Playwright (regla del CLAUDE.md raíz).

## Decisiones de este plan

Elecciones que el pedido y las decisiones de arquitectura dejan abiertas. Se aprueban junto con el plan.

1. **Sin router.** Son pocas pantallas y dependen del estado de la sesión, no de la URL; `App` elige la pantalla. Se agrega un router recién cuando haya navegación real (staff, F6). La semana visible es estado local.
2. **"Hoy" sale del servidor.** La semana inicial se calcula con el campo `ahora` de `GET /api/health` (usa el reloj inyectable, D27) y no con el reloj del navegador, para que el reloj de demo adelantado también mueva el calendario. Si `health` falla, se usa la hora del navegador. Es lectura pública, pero pasa por el mismo cliente y manda el token si lo hay.
3. **Registro en dos pasos con recuperación.** `signUp` en Supabase y después `POST /api/registro` con `{nombre, codigoCoordinacion?}`. Si el segundo paso falla (por ejemplo `CODIGO_INVALIDO`, 422), la cuenta de Supabase ya existe: la app pasa al estado `sin-registro` (el `GET /api/me` responde 403 `USUARIO_NO_REGISTRADO`) y muestra un formulario "Completá tu registro" con nombre y código, con el mensaje del error. Así nadie queda atrapado con una cuenta a medias. El mismo estado cubre a quien cierra la pestaña en el medio.
4. **Coordinadores.** Un COORDINADOR ACTIVO ve el mismo calendario, sin botones de médico (no hace guardias ni se postula, D23), con un aviso de que las pantallas de coordinación llegan más adelante. El pedido es la experiencia del médico.
5. **Estados de la cuenta.** PENDIENTE: "Esperando activación". BAJA: "Tu cuenta está dada de baja". Ambos con "Actualizar" (vuelve a pedir `/api/me`) y "Cerrar sesión". Si cualquier otro pedido responde 403 `CUENTA_PENDIENTE` o `CUENTA_DADA_DE_BAJA` (la cuenta cambió con la app abierta), se vuelve a pedir `/api/me`, que cambia la pantalla.
6. **Sesión inválida.** 401 `TOKEN_VENCIDO`, `TOKEN_INVALIDO` o `SIN_SESION` cierra la sesión de Supabase y vuelve al login con el mensaje del servidor.
7. **Datos simulados** (solo en `src/simulado/`, rótulo "Simulado" visible en el detalle del turno):
   - Un turno de otro titular se simula con aviso de ausencia abierto si `hash(turnoId) % 5 === 0`, y con un postulante simulado si además `% 10 === 0`. Un turno sin titular (`titular: null`) es BAJA y es real (D24); se puede cubrir como cualquier vacante.
   - Urgente (D15) si el aviso está abierto y el inicio dista menos de 24 h de `ahora`.
   - Acciones: titular de un turno futuro sin aviso → "Avisar ausencia" (con motivo, que solo verán los coordinadores, D25); titular con aviso → "Retirar aviso"; otro médico con aviso abierto → "Postularme"; ya postulado → "Retirar postulación". Nunca postularse al propio turno (D16). Turnos que ya terminaron no tienen acciones.
   - Las acciones cambian solo la memoria de la pestaña; no hay llamadas. La superposición de guardias (D16) la validará el backend cuando existan los endpoints; el simulado no la calcula (YAGNI).
8. **Pruebas.** Vitest con jsdom para lógica y componentes (el `auth` de Supabase se inyecta como prop, así los tests no tocan la red). Playwright simula Supabase Auth (`**/auth/v1/**`) y `/api/*` con `page.route` para los flujos de interfaz, y un archivo aparte contra el backend real verifica el contrato (401 `SIN_SESION` sin token). El spec actual de `health` se reemplaza porque la página de inicio ya no muestra el estado del servidor.

## Review Focus

Entradas y condiciones que el pedido no enumera y que más probablemente rompan la app; cada una tiene su prueba en la tarea indicada.

1. **Token vencido o inválido con la app abierta** (401 `TOKEN_VENCIDO`): debe volver al login con el mensaje, no quedar colgada ni mostrar un calendario vacío. Tareas 2 y 4.
2. **Registro a medias** (código incorrecto, cierre de pestaña, error de red entre `signUp` y `/registro`): la cuenta de Supabase existe sin Usuario; la app ofrece completar el registro en vez de pedir otro `signUp` que fallaría con "ya registrado". Tarea 4 y 5.
3. **Turnos que cruzan medianoche y de 24 h** (`inicio` el viernes 20:00, `fin` el sábado 08:00): aparecen el día en que empiezan, con el fin del día siguiente indicado, y el "es hoy" se decide por la fecha en Buenos Aires, no por UTC (un instante `2026-10-17T02:30:00Z` es el 16 a las 23:30). Tarea 3 y 7.
4. **Respuestas que llegan desordenadas** al cambiar de semana rápido: una respuesta vieja no debe pisar la semana actual. Tarea 7.
5. **Servidor caído o lento y semana sin turnos:** mensaje claro con "Reintentar" y estado vacío ("No hay guardias esta semana"), nunca pantalla en blanco. Turno con `titular: null` (BAJA) se muestra sin romper. Tareas 7 y 8.
6. **Doble envío** de login/registro (doble clic): el botón se deshabilita mientras hay un pedido en curso, para no crear dos `signUp`. Tarea 5.

---

## Estructura de archivos

```
frontend/
  package.json                      (modificar: dependencias y script test)
  vite.config.js                    (modificar: bloque test)
  index.html                        (modificar: theme-color)
  src/
    main.jsx                        (modificar: monta SesionProvider)
    App.jsx                         (reemplazar: elige pantalla según el estado de la sesión)
    estilos.css                     (crear)
    lib/
      api.js                        cliente HTTP con Bearer y ErrorApi
      fechas.js                     semana, zona horaria y agrupación por día
      supabase.js                   cliente de supabase-js a partir de VITE_*
      errores-auth.js               traduce errores de Supabase Auth al español
    sesion/
      SesionProvider.jsx            máquina de estados sesión + /api/me
      useSesion.js                  hook de acceso al contexto
    pantallas/
      Acceso.jsx                    login y registro
      CompletarRegistro.jsx         registro a medias (estado sin-registro)
      CuentaSinAcceso.jsx           pendiente y baja
      Calendario.jsx                semana, navegación, detalle
    componentes/
      TarjetaTurno.jsx              un turno en la grilla
      DetalleTurno.jsx              panel con acciones (simuladas)
      Cargando.jsx                  indicador de carga
    simulado/
      vacantes.js                   derivarEstado (puro) y datos simulados
      useVacantesSimuladas.js       overrides en memoria
    pruebas/
      setup.js                      jest-dom
      auth-falso.js                 fábrica de un "auth" de Supabase de mentira
  e2e/
    ayudas.js                       token falso, rutas simuladas de Supabase y API
    medico.spec.js                  flujos de interfaz
    contrato.spec.js                contrato contra el backend real
    health.spec.js                  (borrar)
```

Pruebas unitarias junto al código (`*.test.js` / `*.test.jsx`).

---

### Task 1: Herramientas de prueba y dependencias

**Files:**
- Modify: `frontend/package.json`, `frontend/vite.config.js`
- Create: `frontend/src/pruebas/setup.js`, `frontend/src/lib/humo.test.js` (se borra al final de la tarea)

**Interfaces:**
- Produces: `npm test` (Vitest, una vez), `npm run test:watch`; entorno jsdom con `@testing-library/jest-dom`. Los archivos `src/**/*.test.{js,jsx}` se ejecutan; `e2e/` queda fuera de Vitest.

- [ ] **Step 1: Instalar dependencias**

```bash
cd frontend
npm install @supabase/supabase-js@^2
npm install -D vitest@^3 jsdom@^26 @testing-library/react@^16 @testing-library/user-event@^14 @testing-library/jest-dom@^6
```

- [ ] **Step 2: Scripts y configuración**

En `package.json`, dentro de `scripts`, agregar `"test": "vitest run"` y `"test:watch": "vitest"`.

`frontend/vite.config.js`:

```js
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/pruebas/setup.js"],
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
  },
});
```

`frontend/src/pruebas/setup.js`:

```js
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());
```

- [ ] **Step 3: Prueba de humo para ver que el entorno funciona**

`frontend/src/lib/humo.test.js`:

```js
import { expect, test } from "vitest";

test("el entorno de pruebas tiene DOM", () => {
  document.body.innerHTML = "<p>hola</p>";
  expect(document.body).toHaveTextContent("hola");
});
```

- [ ] **Step 4: Ejecutar**

Run: `npm test`
Expected: 1 passed.

- [ ] **Step 5: Borrar la prueba de humo y confirmar que `npm run build` sigue andando**

```bash
rm src/lib/humo.test.js && npm run build
```

Expected: build OK.

- [ ] **Step 6: Commit**

```bash
git add package.json package-lock.json vite.config.js src/pruebas/setup.js
git commit -m "Frontend: Vitest, Testing Library y supabase-js como dependencias" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Cliente HTTP con Bearer (D06)

**Files:**
- Create: `frontend/src/lib/api.js`
- Test: `frontend/src/lib/api.test.js`

**Interfaces:**
- Produces:
  - `class ErrorApi extends Error { status: number; codigo: string; message: string }` (`message` es el `mensaje` del servidor).
  - `crearClienteApi({ obtenerToken, alSesionInvalida?, fetchImpl? }) → { get(ruta, consulta?), post(ruta, cuerpo?) }`. `obtenerToken: () => Promise<string | null>`. `get`/`post` devuelven el JSON o `undefined` si la respuesta es 204. `ruta` empieza con `/api/`. `consulta` es un objeto que se serializa a querystring (omite `undefined`/`null`).
  - `CODIGOS_SESION_INVALIDA = ["SIN_SESION", "TOKEN_VENCIDO", "TOKEN_INVALIDO"]`; cuando un 401 trae uno de esos códigos se llama `alSesionInvalida(error)` antes de lanzar.
  - Códigos locales: `SIN_SESION` (no hay token; no se hace el pedido), `SIN_CONEXION` (falla de red, `status: 0`).

- [ ] **Step 1: Escribir las pruebas**

```js
import { describe, expect, test, vi } from "vitest";
import { crearClienteApi, ErrorApi } from "./api.js";

function respuesta(status, cuerpo) {
  return new Response(cuerpo === undefined ? null : JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function cliente(opciones = {}) {
  const fetchImpl = opciones.fetchImpl ?? vi.fn().mockResolvedValue(respuesta(200, { ok: true }));
  const api = crearClienteApi({
    obtenerToken: opciones.obtenerToken ?? (async () => "tok-123"),
    alSesionInvalida: opciones.alSesionInvalida,
    fetchImpl,
  });
  return { api, fetchImpl };
}

describe("crearClienteApi", () => {
  test("manda Authorization: Bearer con el token de Supabase en cada pedido", async () => {
    const { api, fetchImpl } = cliente();
    await api.get("/api/me");
    await api.post("/api/registro", { nombre: "Ana" });
    for (const [, opciones] of fetchImpl.mock.calls) {
      expect(opciones.headers.Authorization).toBe("Bearer tok-123");
    }
  });

  test("serializa la consulta y omite valores vacíos", async () => {
    const { api, fetchImpl } = cliente();
    await api.get("/api/turnos", { desde: "2026-10-05", hasta: "2026-10-11", otro: undefined });
    expect(fetchImpl.mock.calls[0][0]).toBe("/api/turnos?desde=2026-10-05&hasta=2026-10-11");
  });

  test("el POST manda JSON", async () => {
    const { api, fetchImpl } = cliente();
    await api.post("/api/registro", { nombre: "Ana", codigoCoordinacion: "SMG" });
    const [, opciones] = fetchImpl.mock.calls[0];
    expect(opciones.method).toBe("POST");
    expect(opciones.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(opciones.body)).toEqual({ nombre: "Ana", codigoCoordinacion: "SMG" });
  });

  test("sin token no hace el pedido y falla con SIN_SESION", async () => {
    const { api, fetchImpl } = cliente({ obtenerToken: async () => null });
    await expect(api.get("/api/me")).rejects.toMatchObject({ codigo: "SIN_SESION", status: 401 });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test("convierte {codigo, mensaje} del servidor en ErrorApi", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(respuesta(422, { codigo: "CODIGO_INVALIDO", mensaje: "El código no es correcto." }));
    const { api } = cliente({ fetchImpl });
    const error = await api.post("/api/registro", {}).catch((e) => e);
    expect(error).toBeInstanceOf(ErrorApi);
    expect(error).toMatchObject({ status: 422, codigo: "CODIGO_INVALIDO", message: "El código no es correcto." });
  });

  test.each(["SIN_SESION", "TOKEN_VENCIDO", "TOKEN_INVALIDO"])("401 %s avisa que la sesión no sirve", async (codigo) => {
    const fetchImpl = vi.fn().mockResolvedValue(respuesta(401, { codigo, mensaje: "Volvé a ingresar." }));
    const alSesionInvalida = vi.fn();
    const { api } = cliente({ fetchImpl, alSesionInvalida });
    await expect(api.get("/api/turnos")).rejects.toMatchObject({ codigo });
    expect(alSesionInvalida).toHaveBeenCalledTimes(1);
  });

  test("un 403 no cierra la sesión", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(respuesta(403, { codigo: "CUENTA_PENDIENTE", mensaje: "Pendiente." }));
    const alSesionInvalida = vi.fn();
    const { api } = cliente({ fetchImpl, alSesionInvalida });
    await expect(api.get("/api/turnos")).rejects.toMatchObject({ codigo: "CUENTA_PENDIENTE" });
    expect(alSesionInvalida).not.toHaveBeenCalled();
  });

  test("falla de red: SIN_CONEXION con mensaje legible", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const { api } = cliente({ fetchImpl });
    await expect(api.get("/api/me")).rejects.toMatchObject({ codigo: "SIN_CONEXION", status: 0 });
  });

  test("error con cuerpo que no es JSON: código HTTP_<status>", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response("<html>Bad gateway</html>", { status: 502 }));
    const { api } = cliente({ fetchImpl });
    await expect(api.get("/api/me")).rejects.toMatchObject({ codigo: "HTTP_502", status: 502 });
  });

  test("204 devuelve undefined", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    const { api } = cliente({ fetchImpl });
    await expect(api.post("/api/x")).resolves.toBeUndefined();
  });
});
```

- [ ] **Step 2: Ver que falla**

Run: `npx vitest run src/lib/api.test.js`
Expected: FAIL (no existe `api.js`).

- [ ] **Step 3: Implementar `frontend/src/lib/api.js`**

```js
export const CODIGOS_SESION_INVALIDA = ["SIN_SESION", "TOKEN_VENCIDO", "TOKEN_INVALIDO"];

export class ErrorApi extends Error {
  constructor(status, codigo, mensaje) {
    super(mensaje);
    this.name = "ErrorApi";
    this.status = status;
    this.codigo = codigo;
  }
}

function conConsulta(ruta, consulta) {
  const parametros = new URLSearchParams();
  for (const [clave, valor] of Object.entries(consulta ?? {})) {
    if (valor !== undefined && valor !== null) parametros.set(clave, String(valor));
  }
  const texto = parametros.toString();
  return texto ? `${ruta}?${texto}` : ruta;
}

export function crearClienteApi({ obtenerToken, alSesionInvalida = () => {}, fetchImpl = (...args) => fetch(...args) }) {
  async function pedir(metodo, ruta, { consulta, cuerpo } = {}) {
    const token = await obtenerToken();
    if (!token) {
      const error = new ErrorApi(401, "SIN_SESION", "Falta el token de sesión.");
      alSesionInvalida(error);
      throw error;
    }
    const headers = { Authorization: `Bearer ${token}` };
    if (cuerpo !== undefined) headers["Content-Type"] = "application/json";

    let respuesta;
    try {
      respuesta = await fetchImpl(conConsulta(ruta, consulta), {
        method: metodo,
        headers,
        body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
      });
    } catch {
      throw new ErrorApi(0, "SIN_CONEXION", "No se pudo conectar con el servidor. Revisá tu conexión.");
    }

    if (respuesta.status === 204) return undefined;
    const datos = await respuesta.json().catch(() => null);
    if (!respuesta.ok) {
      const error = new ErrorApi(
        respuesta.status,
        datos?.codigo ?? `HTTP_${respuesta.status}`,
        datos?.mensaje ?? `El servidor respondió con error ${respuesta.status}.`,
      );
      if (respuesta.status === 401 && CODIGOS_SESION_INVALIDA.includes(error.codigo)) alSesionInvalida(error);
      throw error;
    }
    return datos ?? undefined;
  }

  return {
    get: (ruta, consulta) => pedir("GET", ruta, { consulta }),
    post: (ruta, cuerpo) => pedir("POST", ruta, { cuerpo }),
  };
}
```

- [ ] **Step 4: Ver que pasa**

Run: `npx vitest run src/lib/api.test.js`
Expected: todas PASS. Nota: el caso "sin token" también llama a `alSesionInvalida` (la sesión no sirve); la prueba no lo prohíbe.

- [ ] **Step 5: Commit**

```bash
git add src/lib/api.js src/lib/api.test.js
git commit -m "Frontend: cliente HTTP que manda el token de Supabase en cada pedido (D06)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Fechas y semana en hora de Buenos Aires (D13)

**Files:**
- Create: `frontend/src/lib/fechas.js`
- Test: `frontend/src/lib/fechas.test.js`

**Interfaces:**
- Produces (todas puras; las fechas son strings `"YYYY-MM-DD"` salvo indicación):
  - `ZONA = "America/Argentina/Buenos_Aires"`
  - `fechaLocal(instante: string | Date) → "YYYY-MM-DD"` (fecha calendario en Buenos Aires)
  - `horaLocal(instante: string | Date) → "HH:mm"` (24 h, Buenos Aires)
  - `sumarDias(fecha, n) → fecha`
  - `lunesDe(fecha) → fecha` (lunes de esa semana; el domingo pertenece a la semana que termina)
  - `diasDeSemana(lunes) → string[7]`
  - `rangoSemana(lunes) → { desde, hasta }` (lunes y domingo)
  - `agruparPorDia(turnos, dias) → Record<fecha, turno[]>` (clave para cada día de `dias`, ordenado por `inicio`; descarta turnos fuera de `dias`)
  - `etiquetaDia(fecha) → "lun 5"`; `etiquetaSemana(lunes) → "5 al 11 de octubre de 2026"`
  - `terminoAntes(turno, ahora) → boolean` (el `fin` es anterior a `ahora`)
  - `horasHasta(turno, ahora) → number` (horas desde `ahora` hasta `inicio`; negativo si ya empezó)

- [ ] **Step 1: Escribir las pruebas**

```js
import { describe, expect, test } from "vitest";
import {
  agruparPorDia, diasDeSemana, etiquetaDia, etiquetaSemana, fechaLocal, horaLocal, horasHasta,
  lunesDe, rangoSemana, sumarDias, terminoAntes,
} from "./fechas.js";

describe("semana (empieza el lunes)", () => {
  test.each([
    ["2026-10-05", "2026-10-05"], // lunes
    ["2026-10-07", "2026-10-05"], // miércoles
    ["2026-10-11", "2026-10-05"], // domingo pertenece a la semana que termina
    ["2026-10-12", "2026-10-12"],
  ])("lunesDe(%s) = %s", (fecha, esperado) => {
    expect(lunesDe(fecha)).toBe(esperado);
  });

  test("sumarDias cruza mes y año", () => {
    expect(sumarDias("2026-10-30", 3)).toBe("2026-11-02");
    expect(sumarDias("2026-12-31", 1)).toBe("2027-01-01");
    expect(sumarDias("2026-10-05", -7)).toBe("2026-09-28");
  });

  test("diasDeSemana y rangoSemana", () => {
    expect(diasDeSemana("2026-10-05")).toEqual([
      "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11",
    ]);
    expect(rangoSemana("2026-10-05")).toEqual({ desde: "2026-10-05", hasta: "2026-10-11" });
  });
});

describe("zona horaria de Buenos Aires", () => {
  test("fechaLocal usa la fecha de Buenos Aires, no la de UTC", () => {
    expect(fechaLocal("2026-10-17T02:30:00Z")).toBe("2026-10-16"); // 23:30 del 16 en Buenos Aires
    expect(fechaLocal("2026-10-17T08:00:00-03:00")).toBe("2026-10-17");
  });

  test("horaLocal en 24 h", () => {
    expect(horaLocal("2026-10-17T08:00:00-03:00")).toBe("08:00");
    expect(horaLocal("2026-10-17T20:30:00-03:00")).toBe("20:30");
    expect(horaLocal("2026-10-17T00:00:00-03:00")).toBe("00:00");
  });
});

describe("etiquetas", () => {
  test("etiquetaDia", () => {
    expect(etiquetaDia("2026-10-05")).toBe("lun 5");
    expect(etiquetaDia("2026-10-11")).toBe("dom 11");
  });
  test("etiquetaSemana dentro de un mes y entre meses", () => {
    expect(etiquetaSemana("2026-10-05")).toBe("5 al 11 de octubre de 2026");
    expect(etiquetaSemana("2026-10-26")).toBe("26 de octubre al 1 de noviembre de 2026");
    expect(etiquetaSemana("2026-12-28")).toBe("28 de diciembre de 2026 al 3 de enero de 2027");
  });
});

describe("agruparPorDia", () => {
  const dias = diasDeSemana("2026-10-05");
  const turno = (id, fecha, inicio) => ({ id, fecha, inicio, fin: inicio });

  test("todos los días tienen clave y los turnos van ordenados por inicio", () => {
    const grupos = agruparPorDia(
      [
        turno("b", "2026-10-06", "2026-10-06T20:00:00-03:00"),
        turno("a", "2026-10-06", "2026-10-06T08:00:00-03:00"),
      ],
      dias,
    );
    expect(Object.keys(grupos)).toEqual(dias);
    expect(grupos["2026-10-06"].map((t) => t.id)).toEqual(["a", "b"]);
    expect(grupos["2026-10-05"]).toEqual([]);
  });

  test("un turno que empieza el domingo y termina el lunes figura en el domingo", () => {
    const t = { id: "n", fecha: "2026-10-11", inicio: "2026-10-11T20:00:00-03:00", fin: "2026-10-12T08:00:00-03:00" };
    const grupos = agruparPorDia([t], dias);
    expect(grupos["2026-10-11"]).toEqual([t]);
  });

  test("ignora turnos fuera de la semana", () => {
    const grupos = agruparPorDia([turno("x", "2026-10-20", "2026-10-20T08:00:00-03:00")], dias);
    expect(Object.values(grupos).flat()).toEqual([]);
  });
});

describe("tiempo relativo a ahora", () => {
  const t = { inicio: "2026-10-10T08:00:00-03:00", fin: "2026-10-10T16:00:00-03:00" };
  test("terminoAntes", () => {
    expect(terminoAntes(t, "2026-10-10T16:00:01-03:00")).toBe(true);
    expect(terminoAntes(t, "2026-10-10T12:00:00-03:00")).toBe(false);
  });
  test("horasHasta", () => {
    expect(horasHasta(t, "2026-10-09T20:00:00-03:00")).toBe(12);
    expect(horasHasta(t, "2026-10-10T10:00:00-03:00")).toBe(-2);
  });
});
```

- [ ] **Step 2: Ver que falla** (`npx vitest run src/lib/fechas.test.js` → FAIL, no existe el módulo).

- [ ] **Step 3: Implementar `frontend/src/lib/fechas.js`**

```js
export const ZONA = "America/Argentina/Buenos_Aires";

const formatoFecha = new Intl.DateTimeFormat("en-CA", { timeZone: ZONA, year: "numeric", month: "2-digit", day: "2-digit" });
const formatoHora = new Intl.DateTimeFormat("es-AR", { timeZone: ZONA, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const DIAS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];

export function fechaLocal(instante) {
  return formatoFecha.format(new Date(instante));
}

export function horaLocal(instante) {
  return formatoHora.format(new Date(instante));
}

// Las fechas calendario se manejan como UTC a medianoche solo para hacer cuentas de días; no son instantes.
function aUtc(fecha) {
  const [anio, mes, dia] = fecha.split("-").map(Number);
  return new Date(Date.UTC(anio, mes - 1, dia));
}

function deUtc(date) {
  return date.toISOString().slice(0, 10);
}

export function sumarDias(fecha, n) {
  const date = aUtc(fecha);
  date.setUTCDate(date.getUTCDate() + n);
  return deUtc(date);
}

export function lunesDe(fecha) {
  const diaSemana = aUtc(fecha).getUTCDay(); // 0 = domingo
  return sumarDias(fecha, -((diaSemana + 6) % 7));
}

export function diasDeSemana(lunes) {
  return Array.from({ length: 7 }, (_, i) => sumarDias(lunes, i));
}

export function rangoSemana(lunes) {
  return { desde: lunes, hasta: sumarDias(lunes, 6) };
}

export function agruparPorDia(turnos, dias) {
  const grupos = Object.fromEntries(dias.map((dia) => [dia, []]));
  for (const turno of turnos) {
    if (turno.fecha in grupos) grupos[turno.fecha].push(turno);
  }
  for (const lista of Object.values(grupos)) {
    lista.sort((a, b) => new Date(a.inicio) - new Date(b.inicio));
  }
  return grupos;
}

export function etiquetaDia(fecha) {
  const date = aUtc(fecha);
  return `${DIAS[date.getUTCDay()]} ${date.getUTCDate()}`;
}

export function etiquetaSemana(lunes) {
  const a = aUtc(lunes);
  const b = aUtc(sumarDias(lunes, 6));
  const mismoMes = a.getUTCMonth() === b.getUTCMonth();
  const mismoAnio = a.getUTCFullYear() === b.getUTCFullYear();
  const izquierda = mismoMes ? `${a.getUTCDate()}` : `${a.getUTCDate()} de ${MESES[a.getUTCMonth()]}${mismoAnio ? "" : ` de ${a.getUTCFullYear()}`}`;
  return `${izquierda} al ${b.getUTCDate()} de ${MESES[b.getUTCMonth()]} de ${b.getUTCFullYear()}`;
}

export function terminoAntes(turno, ahora) {
  return new Date(turno.fin) < new Date(ahora);
}

export function horasHasta(turno, ahora) {
  return (new Date(turno.inicio) - new Date(ahora)) / 3_600_000;
}
```

- [ ] **Step 4: Ver que pasa** (`npx vitest run src/lib/fechas.test.js` → PASS).

- [ ] **Step 5: Commit**

```bash
git add src/lib/fechas.js src/lib/fechas.test.js
git commit -m "Frontend: fechas y semana en hora de Buenos Aires (D13)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Sesión de Supabase Auth y estado de la cuenta

**Files:**
- Create: `frontend/src/lib/supabase.js`, `frontend/src/lib/errores-auth.js`, `frontend/src/sesion/SesionProvider.jsx`, `frontend/src/sesion/useSesion.js`, `frontend/src/pruebas/auth-falso.js`
- Test: `frontend/src/lib/errores-auth.test.js`, `frontend/src/sesion/SesionProvider.test.jsx`

**Interfaces:**
- Consumes: `crearClienteApi`, `ErrorApi` (Task 2).
- Produces:
  - `traducirErrorAuth(error) → string` (mensaje en español).
  - `crearAuthSupabase() → auth` (`supabase.auth` real; lanza `Error` con mensaje claro si faltan `VITE_SUPABASE_URL` o `VITE_SUPABASE_ANON_KEY`).
  - Contrato mínimo de `auth` (lo que usa el provider y lo que imita el falso): `getSession() → {data:{session}}`, `onAuthStateChange(cb) → {data:{subscription:{unsubscribe}}}` con `cb(evento, session)`, `signInWithPassword({email,password}) → {data:{session}, error}`, `signUp({email,password,options}) → {data:{session}, error}`, `signOut()`.
  - `crearAuthFalso({ sesion? }) → auth` con espías (`vi.fn`) y utilidades `emitir(evento, sesion)`; `sesionFalsa(email="ana@x.com") → {access_token:"tok-"+email, user:{email}}`.
  - `<SesionProvider auth={auth} fetchImpl?>` y `useSesion() → { estado, usuario, aviso, api, iniciarSesion(email, password), registrarse({nombre, email, password, codigo}), completarRegistro({nombre, codigo}), recargar(), cerrarSesion() }`.
  - `estado`: `"cargando" | "anonimo" | "sin-registro" | "activo" | "pendiente" | "baja" | "error"`. `usuario`: respuesta de `GET /api/me` (`{id, nombre, email, rol, estado}`) o `null`. `aviso`: mensaje para mostrar en `anonimo` (sesión vencida) o en `sin-registro` (falló el registro), o `null`. `error` (estado `"error"`): `usuario` es `null` y `aviso` trae el mensaje (servidor caído).
  - `iniciarSesion`, `registrarse` y `completarRegistro` lanzan `Error` con mensaje en español si fallan (la pantalla lo muestra); `registrarse` que falla después de crear la cuenta deja el estado en `sin-registro` con `aviso` y no lanza.

- [ ] **Step 1: Prueba de `errores-auth`**

```js
import { expect, test } from "vitest";
import { traducirErrorAuth } from "./errores-auth.js";

test.each([
  [{ code: "invalid_credentials", message: "Invalid login credentials" }, "Email o contraseña incorrectos."],
  [{ message: "Invalid login credentials" }, "Email o contraseña incorrectos."],
  [{ code: "user_already_exists", message: "User already registered" }, "Ese email ya tiene una cuenta. Ingresá con tu contraseña."],
  [{ message: "User already registered" }, "Ese email ya tiene una cuenta. Ingresá con tu contraseña."],
  [{ code: "weak_password", message: "Password should be at least 6 characters" }, "La contraseña es muy débil: usá al menos 6 caracteres."],
  [{ code: "over_request_rate_limit", message: "x" }, "Demasiados intentos. Esperá un momento y probá de nuevo."],
  [{ name: "AuthRetryableFetchError", message: "Failed to fetch" }, "No se pudo conectar con el servicio de ingreso. Revisá tu conexión."],
  [{ message: "algo raro" }, "No se pudo completar la operación. Probá de nuevo."],
])("traduce %j", (error, esperado) => {
  expect(traducirErrorAuth(error)).toBe(esperado);
});
```

- [ ] **Step 2: Implementar `frontend/src/lib/errores-auth.js`**

```js
const GENERICO = "No se pudo completar la operación. Probá de nuevo.";

export function traducirErrorAuth(error) {
  const codigo = error?.code ?? "";
  const mensaje = error?.message ?? "";
  if (codigo === "invalid_credentials" || /invalid login credentials/i.test(mensaje)) return "Email o contraseña incorrectos.";
  if (codigo === "user_already_exists" || /already registered/i.test(mensaje)) return "Ese email ya tiene una cuenta. Ingresá con tu contraseña.";
  if (codigo === "weak_password" || /password should be/i.test(mensaje)) return "La contraseña es muy débil: usá al menos 6 caracteres.";
  if (codigo === "over_request_rate_limit" || codigo === "over_email_send_rate_limit" || error?.status === 429) {
    return "Demasiados intentos. Esperá un momento y probá de nuevo.";
  }
  if (error?.name === "AuthRetryableFetchError" || /failed to fetch|network/i.test(mensaje)) {
    return "No se pudo conectar con el servicio de ingreso. Revisá tu conexión.";
  }
  return GENERICO;
}
```

- [ ] **Step 3: `frontend/src/lib/supabase.js`**

```js
import { createClient } from "@supabase/supabase-js";

// Supabase se usa solo para el login (D06, D07): los datos van por /api con el token de la sesión.
export function crearAuthSupabase() {
  const url = import.meta.env.VITE_SUPABASE_URL;
  const clave = import.meta.env.VITE_SUPABASE_ANON_KEY;
  if (!url || !clave) {
    throw new Error("Falta configurar VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY en frontend/.env.");
  }
  return createClient(url, clave).auth;
}
```

- [ ] **Step 4: `frontend/src/pruebas/auth-falso.js`**

```js
import { vi } from "vitest";

export function sesionFalsa(email = "ana@x.com") {
  return { access_token: `tok-${email}`, user: { email } };
}

export function crearAuthFalso({ sesion = null } = {}) {
  let actual = sesion;
  const oyentes = new Set();
  const emitir = (evento, nueva) => {
    actual = nueva;
    oyentes.forEach((cb) => cb(evento, nueva));
  };
  return {
    emitir,
    getSession: vi.fn(async () => ({ data: { session: actual } })),
    onAuthStateChange: vi.fn((cb) => {
      oyentes.add(cb);
      return { data: { subscription: { unsubscribe: () => oyentes.delete(cb) } } };
    }),
    signInWithPassword: vi.fn(async ({ email }) => {
      const nueva = sesionFalsa(email);
      emitir("SIGNED_IN", nueva);
      return { data: { session: nueva }, error: null };
    }),
    signUp: vi.fn(async ({ email }) => {
      const nueva = sesionFalsa(email);
      emitir("SIGNED_IN", nueva);
      return { data: { session: nueva }, error: null };
    }),
    signOut: vi.fn(async () => {
      emitir("SIGNED_OUT", null);
      return { error: null };
    }),
  };
}
```

- [ ] **Step 5: Pruebas del provider** `frontend/src/sesion/SesionProvider.test.jsx`

Se usa un componente sonda que muestra `estado`, `usuario?.nombre` y `aviso`, y botones que llaman a las funciones. `fetchImpl` se arma con una tabla ruta → respuesta.

```jsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { crearAuthFalso, sesionFalsa } from "../pruebas/auth-falso.js";
import { SesionProvider } from "./SesionProvider.jsx";
import { useSesion } from "./useSesion.js";

const json = (status, cuerpo) =>
  new Response(JSON.stringify(cuerpo), { status, headers: { "Content-Type": "application/json" } });
const ME_ACTIVO = { id: 1, nombre: "Ana", email: "ana@x.com", rol: "MEDICO", estado: "ACTIVO" };

function Sonda() {
  const s = useSesion();
  return (
    <div>
      <p data-testid="estado">{s.estado}</p>
      <p data-testid="nombre">{s.usuario?.nombre ?? ""}</p>
      <p data-testid="aviso">{s.aviso ?? ""}</p>
      <button onClick={() => s.iniciarSesion("ana@x.com", "secreto1").catch((e) => (document.title = e.message))}>entrar</button>
      <button onClick={() => s.registrarse({ nombre: "Ana", email: "ana@x.com", password: "secreto1", codigo: "SMG" })}>registrar</button>
      <button onClick={() => s.completarRegistro({ nombre: "Ana", codigo: "" })}>completar</button>
      <button onClick={() => s.cerrarSesion()}>salir</button>
    </div>
  );
}

function montar({ auth, rutas }) {
  const fetchImpl = vi.fn(async (url, opciones) => {
    const manejador = rutas[`${opciones.method} ${url}`];
    if (!manejador) throw new Error(`Ruta no simulada: ${opciones.method} ${url}`);
    return manejador(opciones);
  });
  render(
    <SesionProvider auth={auth} fetchImpl={fetchImpl}>
      <Sonda />
    </SesionProvider>,
  );
  return { fetchImpl };
}

describe("SesionProvider", () => {
  test("sin sesión de Supabase: anónimo y no llama a la API", async () => {
    const { fetchImpl } = montar({ auth: crearAuthFalso(), rutas: {} });
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("anonimo"));
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test("con sesión, pide /api/me con Bearer y queda activo", async () => {
    const { fetchImpl } = montar({
      auth: crearAuthFalso({ sesion: sesionFalsa() }),
      rutas: { "GET /api/me": () => json(200, ME_ACTIVO) },
    });
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("activo"));
    expect(screen.getByTestId("nombre")).toHaveTextContent("Ana");
    expect(fetchImpl.mock.calls[0][1].headers.Authorization).toBe("Bearer tok-ana@x.com");
  });

  test.each([
    ["PENDIENTE", "pendiente"],
    ["BAJA", "baja"],
  ])("usuario %s -> estado %s", async (estadoApi, esperado) => {
    montar({
      auth: crearAuthFalso({ sesion: sesionFalsa() }),
      rutas: { "GET /api/me": () => json(200, { ...ME_ACTIVO, estado: estadoApi }) },
    });
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent(esperado));
  });

  test("cuenta de Supabase sin Usuario (403 USUARIO_NO_REGISTRADO) -> sin-registro", async () => {
    montar({
      auth: crearAuthFalso({ sesion: sesionFalsa() }),
      rutas: { "GET /api/me": () => json(403, { codigo: "USUARIO_NO_REGISTRADO", mensaje: "Falta registro." }) },
    });
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("sin-registro"));
  });

  test("token vencido: cierra la sesión de Supabase y vuelve a anónimo con el aviso", async () => {
    const auth = crearAuthFalso({ sesion: sesionFalsa() });
    montar({
      auth,
      rutas: { "GET /api/me": () => json(401, { codigo: "TOKEN_VENCIDO", mensaje: "La sesión venció. Volvé a ingresar." }) },
    });
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("anonimo"));
    expect(auth.signOut).toHaveBeenCalled();
    expect(screen.getByTestId("aviso")).toHaveTextContent("La sesión venció. Volvé a ingresar.");
  });

  test("servidor caído: estado error con aviso", async () => {
    montar({
      auth: crearAuthFalso({ sesion: sesionFalsa() }),
      rutas: { "GET /api/me": () => { throw new TypeError("Failed to fetch"); } },
    });
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("error"));
    expect(screen.getByTestId("aviso")).toHaveTextContent("No se pudo conectar con el servidor");
  });

  test("login: signInWithPassword y luego /api/me", async () => {
    const auth = crearAuthFalso();
    montar({ auth, rutas: { "GET /api/me": () => json(200, ME_ACTIVO) } });
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("anonimo"));
    await userEvent.click(screen.getByText("entrar"));
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("activo"));
    expect(auth.signInWithPassword).toHaveBeenCalledWith({ email: "ana@x.com", password: "secreto1" });
  });

  test("login con credenciales malas lanza el mensaje traducido y queda anónimo", async () => {
    const auth = crearAuthFalso();
    auth.signInWithPassword.mockResolvedValueOnce({ data: { session: null }, error: { code: "invalid_credentials", message: "Invalid login credentials" } });
    montar({ auth, rutas: {} });
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("anonimo"));
    await userEvent.click(screen.getByText("entrar"));
    await waitFor(() => expect(document.title).toBe("Email o contraseña incorrectos."));
    expect(screen.getByTestId("estado")).toHaveTextContent("anonimo");
  });

  test("registro con código: signUp, POST /api/registro con codigoCoordinacion y luego /api/me (sin /me antes del registro)", async () => {
    const llamadas = [];
    const auth = crearAuthFalso();
    montar({
      auth,
      rutas: {
        "POST /api/registro": (opciones) => {
          llamadas.push(["registro", JSON.parse(opciones.body)]);
          return json(201, { ...ME_ACTIVO, rol: "COORDINADOR" });
        },
        "GET /api/me": () => {
          llamadas.push(["me"]);
          return json(200, { ...ME_ACTIVO, rol: "COORDINADOR" });
        },
      },
    });
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("anonimo"));
    await userEvent.click(screen.getByText("registrar"));
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("activo"));
    expect(auth.signUp).toHaveBeenCalledWith(expect.objectContaining({ email: "ana@x.com", password: "secreto1" }));
    expect(llamadas[0]).toEqual(["registro", { nombre: "Ana", codigoCoordinacion: "SMG" }]);
    expect(llamadas.filter(([n]) => n === "me")).toHaveLength(1);
  });

  test("registro sin código no manda codigoCoordinacion", async () => {
    const cuerpos = [];
    const auth = crearAuthFalso();
    montar({
      auth,
      rutas: {
        "POST /api/registro": (opciones) => {
          cuerpos.push(JSON.parse(opciones.body));
          return json(201, { ...ME_ACTIVO, estado: "PENDIENTE" });
        },
        "GET /api/me": () => json(200, { ...ME_ACTIVO, estado: "PENDIENTE" }),
      },
    });
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("anonimo"));
    // la sonda manda código "SMG"; para este caso se usa completarRegistro con código vacío sobre una cuenta ya creada
    auth.emitir("SIGNED_IN", sesionFalsa());
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("pendiente"));
    expect(cuerpos).toEqual([]);
  });

  test("código incorrecto: la cuenta de Supabase queda y la app pasa a sin-registro con el mensaje", async () => {
    const auth = crearAuthFalso();
    montar({
      auth,
      rutas: {
        "POST /api/registro": () => json(422, { codigo: "CODIGO_INVALIDO", mensaje: "El código de coordinación no es correcto." }),
        "GET /api/me": () => json(403, { codigo: "USUARIO_NO_REGISTRADO", mensaje: "Falta registro." }),
      },
    });
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("anonimo"));
    await userEvent.click(screen.getByText("registrar"));
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("sin-registro"));
    expect(screen.getByTestId("aviso")).toHaveTextContent("El código de coordinación no es correcto.");
    expect(auth.signOut).not.toHaveBeenCalled();
  });

  test("completarRegistro manda solo el nombre cuando no hay código", async () => {
    const cuerpos = [];
    montar({
      auth: crearAuthFalso({ sesion: sesionFalsa() }),
      rutas: {
        "GET /api/me": (() => {
          let primera = true;
          return () => {
            if (primera) { primera = false; return json(403, { codigo: "USUARIO_NO_REGISTRADO", mensaje: "x" }); }
            return json(200, { ...ME_ACTIVO, estado: "PENDIENTE" });
          };
        })(),
        "POST /api/registro": (opciones) => { cuerpos.push(JSON.parse(opciones.body)); return json(201, ME_ACTIVO); },
      },
    });
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("sin-registro"));
    await userEvent.click(screen.getByText("completar"));
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("pendiente"));
    expect(cuerpos).toEqual([{ nombre: "Ana" }]);
  });

  test("cerrar sesión vuelve a anónimo", async () => {
    const auth = crearAuthFalso({ sesion: sesionFalsa() });
    montar({ auth, rutas: { "GET /api/me": () => json(200, ME_ACTIVO) } });
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("activo"));
    await userEvent.click(screen.getByText("salir"));
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("anonimo"));
    expect(screen.getByTestId("nombre")).toHaveTextContent("");
  });
});
```

- [ ] **Step 6: Ver que falla** (`npx vitest run src/lib/errores-auth.test.js src/sesion` → `errores-auth` pasa tras Step 2; el provider falla porque no existe).

- [ ] **Step 7: Implementar `frontend/src/sesion/useSesion.js`**

```js
import { createContext, useContext } from "react";

export const ContextoSesion = createContext(null);

export function useSesion() {
  const contexto = useContext(ContextoSesion);
  if (!contexto) throw new Error("useSesion se usa dentro de <SesionProvider>.");
  return contexto;
}
```

- [ ] **Step 8: Implementar `frontend/src/sesion/SesionProvider.jsx`**

```jsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { crearClienteApi, ErrorApi } from "../lib/api.js";
import { traducirErrorAuth } from "../lib/errores-auth.js";
import { ContextoSesion } from "./useSesion.js";

const ESTADO_DE_CUENTA = { ACTIVO: "activo", PENDIENTE: "pendiente", BAJA: "baja" };

export function SesionProvider({ auth, fetchImpl, children }) {
  const [estado, setEstado] = useState("cargando");
  const [usuario, setUsuario] = useState(null);
  const [aviso, setAviso] = useState(null);
  const registrando = useRef(false);
  // El estado anterior evita que un 401 repetido de varios pedidos cierre la sesión dos veces.
  const cerrandoPorToken = useRef(false);

  const cerrarPorTokenInvalido = useCallback(
    async (error) => {
      if (cerrandoPorToken.current) return;
      cerrandoPorToken.current = true;
      try {
        await auth.signOut();
      } finally {
        cerrandoPorToken.current = false;
        setUsuario(null);
        setAviso(error.message);
        setEstado("anonimo");
      }
    },
    [auth],
  );

  const api = useMemo(
    () =>
      crearClienteApi({
        obtenerToken: async () => (await auth.getSession()).data.session?.access_token ?? null,
        alSesionInvalida: cerrarPorTokenInvalido,
        fetchImpl,
      }),
    [auth, fetchImpl, cerrarPorTokenInvalido],
  );

  const cargarUsuario = useCallback(async () => {
    const { data } = await auth.getSession();
    if (!data.session) {
      setUsuario(null);
      setEstado("anonimo");
      return;
    }
    try {
      const yo = await api.get("/api/me");
      setUsuario(yo);
      setAviso(null);
      setEstado(ESTADO_DE_CUENTA[yo.estado] ?? "error");
    } catch (error) {
      if (!(error instanceof ErrorApi)) throw error;
      if (error.codigo === "USUARIO_NO_REGISTRADO") {
        setUsuario(null);
        setEstado("sin-registro");
      } else if (error.status === 401) {
        // api.js ya avisó a cerrarPorTokenInvalido
      } else {
        setUsuario(null);
        setAviso(error.message);
        setEstado("error");
      }
    }
  }, [auth, api]);

  useEffect(() => {
    cargarUsuario();
    const { data } = auth.onAuthStateChange((evento, sesion) => {
      if (registrando.current) return; // el registro en curso carga el usuario al terminar
      if (evento === "SIGNED_OUT" || !sesion) {
        setUsuario(null);
        setEstado((previo) => (previo === "cargando" ? "anonimo" : "anonimo"));
      } else if (evento === "SIGNED_IN") {
        cargarUsuario();
      }
    });
    return () => data.subscription.unsubscribe();
  }, [auth, cargarUsuario]);

  const iniciarSesion = useCallback(
    async (email, password) => {
      const { error } = await auth.signInWithPassword({ email, password });
      if (error) throw new Error(traducirErrorAuth(error));
      setAviso(null);
    },
    [auth],
  );

  const enviarRegistro = useCallback(
    async (nombre, codigo) => {
      const cuerpo = { nombre: nombre.trim() };
      if (codigo?.trim()) cuerpo.codigoCoordinacion = codigo.trim();
      await api.post("/api/registro", cuerpo);
    },
    [api],
  );

  const registrarse = useCallback(
    async ({ nombre, email, password, codigo }) => {
      registrando.current = true;
      try {
        const { data, error } = await auth.signUp({ email, password, options: { data: { nombre } } });
        if (error) throw new Error(traducirErrorAuth(error));
        if (!data.session) {
          throw new Error("Tu cuenta se creó pero Supabase pide confirmar el email antes de ingresar. Avisale al equipo.");
        }
        try {
          await enviarRegistro(nombre, codigo);
          setAviso(null);
        } catch (errorRegistro) {
          if (!(errorRegistro instanceof ErrorApi)) throw errorRegistro;
          if (errorRegistro.status !== 401) setAviso(errorRegistro.message);
        }
      } finally {
        registrando.current = false;
      }
      await cargarUsuario();
    },
    [auth, enviarRegistro, cargarUsuario],
  );

  const completarRegistro = useCallback(
    async ({ nombre, codigo }) => {
      try {
        await enviarRegistro(nombre, codigo);
      } catch (error) {
        if (error instanceof ErrorApi && error.status !== 401) throw new Error(error.message);
        throw error;
      }
      setAviso(null);
      await cargarUsuario();
    },
    [enviarRegistro, cargarUsuario],
  );

  const cerrarSesion = useCallback(async () => {
    await auth.signOut();
    setUsuario(null);
    setAviso(null);
    setEstado("anonimo");
  }, [auth]);

  const valor = useMemo(
    () => ({ estado, usuario, aviso, api, iniciarSesion, registrarse, completarRegistro, recargar: cargarUsuario, cerrarSesion }),
    [estado, usuario, aviso, api, iniciarSesion, registrarse, completarRegistro, cargarUsuario, cerrarSesion],
  );

  return <ContextoSesion.Provider value={valor}>{children}</ContextoSesion.Provider>;
}
```

Limpieza antes de correr las pruebas: reemplazar la línea `setEstado((previo) => (previo === "cargando" ? "anonimo" : "anonimo"));` por `setEstado("anonimo");` (el condicional era redundante).

Caso `registrarse` donde `signUp` crea la cuenta pero `registro` falla con 409 `YA_REGISTRADO`/`EMAIL_YA_REGISTRADO`: el mensaje del servidor queda en `aviso` y `cargarUsuario()` define el estado real; no hace falta código especial.

- [ ] **Step 9: Ver que pasa**

Run: `npx vitest run src/lib/errores-auth.test.js src/sesion`
Expected: PASS. Si "registro sin código no manda codigoCoordinacion" resulta confuso porque la sonda no lo ejercita, reescribirlo para que ejercite `completarRegistro` con código vacío (ya cubierto en la última prueba de `completarRegistro`) y borrar la prueba redundante.

- [ ] **Step 10: Commit**

```bash
git add src/lib src/sesion src/pruebas/auth-falso.js
git commit -m "Frontend: sesión de Supabase Auth y estado de la cuenta con /api/me (D06, D30)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Pantallas de acceso, registro a medias y cuenta sin acceso

**Files:**
- Create: `frontend/src/pantallas/Acceso.jsx`, `frontend/src/pantallas/CompletarRegistro.jsx`, `frontend/src/pantallas/CuentaSinAcceso.jsx`, `frontend/src/componentes/Cargando.jsx`, `frontend/src/estilos.css`
- Test: `frontend/src/pantallas/Acceso.test.jsx`, `frontend/src/pantallas/CuentaSinAcceso.test.jsx`

**Interfaces:**
- Consumes: `useSesion()` (Task 4): `iniciarSesion`, `registrarse`, `completarRegistro`, `recargar`, `cerrarSesion`, `aviso`, `usuario`, `estado`.
- Produces: `<Acceso />`, `<CompletarRegistro />`, `<CuentaSinAcceso />` (sin props; leen el contexto), `<Cargando texto? />`.
- Accesibilidad que usan las pruebas y el e2e: campos con `<label>` ("Nombre", "Email", "Contraseña", "Código de coordinación (opcional)"); botones "Ingresar" / "Crear cuenta"; pestañas con `role="tab"` ("Ingresar", "Registrarme"); errores en `role="alert"`; texto "Esperando activación".

- [ ] **Step 1: Pruebas de `Acceso`**

Helper que monta `<ContextoSesion.Provider value={...}>` con funciones `vi.fn` (sin provider real) para probar solo la pantalla.

```jsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { ContextoSesion } from "../sesion/useSesion.js";
import Acceso from "./Acceso.jsx";

function montar(valor = {}) {
  const contexto = {
    estado: "anonimo", usuario: null, aviso: null,
    iniciarSesion: vi.fn().mockResolvedValue(undefined),
    registrarse: vi.fn().mockResolvedValue(undefined),
    ...valor,
  };
  render(<ContextoSesion.Provider value={contexto}><Acceso /></ContextoSesion.Provider>);
  return contexto;
}

describe("Acceso", () => {
  test("ingresar manda email y contraseña", async () => {
    const ctx = montar();
    await userEvent.type(screen.getByLabelText("Email"), "ana@x.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "secreto1");
    await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    expect(ctx.iniciarSesion).toHaveBeenCalledWith("ana@x.com", "secreto1");
  });

  test("muestra el error de ingreso en un alert", async () => {
    montar({ iniciarSesion: vi.fn().mockRejectedValue(new Error("Email o contraseña incorrectos.")) });
    await userEvent.type(screen.getByLabelText("Email"), "ana@x.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "mala");
    await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email o contraseña incorrectos.");
  });

  test("muestra el aviso de sesión vencida", () => {
    montar({ aviso: "La sesión venció. Volvé a ingresar." });
    expect(screen.getByRole("status")).toHaveTextContent("La sesión venció. Volvé a ingresar.");
  });

  test("registro: el código de coordinación es opcional y sin él no se manda", async () => {
    const ctx = montar();
    await userEvent.click(screen.getByRole("tab", { name: "Registrarme" }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Ana Gómez");
    await userEvent.type(screen.getByLabelText("Email"), "ana@x.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "secreto1");
    expect(screen.getByLabelText("Código de coordinación (opcional)")).toHaveValue("");
    await userEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(ctx.registrarse).toHaveBeenCalledWith({ nombre: "Ana Gómez", email: "ana@x.com", password: "secreto1", codigo: "" });
  });

  test("registro con código lo envía", async () => {
    const ctx = montar();
    await userEvent.click(screen.getByRole("tab", { name: "Registrarme" }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Enzo");
    await userEvent.type(screen.getByLabelText("Email"), "enzo@x.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "secreto1");
    await userEvent.type(screen.getByLabelText("Código de coordinación (opcional)"), "SMG");
    await userEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(ctx.registrarse).toHaveBeenCalledWith(expect.objectContaining({ codigo: "SMG" }));
  });

  test("la contraseña exige 6 caracteres en el registro (el formulario no se envía antes)", async () => {
    const ctx = montar();
    await userEvent.click(screen.getByRole("tab", { name: "Registrarme" }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Ana");
    await userEvent.type(screen.getByLabelText("Email"), "ana@x.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "123");
    await userEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(ctx.registrarse).not.toHaveBeenCalled();
  });

  test("doble clic no envía dos veces: el botón se deshabilita mientras espera", async () => {
    let resolver;
    const iniciarSesion = vi.fn(() => new Promise((r) => { resolver = r; }));
    montar({ iniciarSesion });
    await userEvent.type(screen.getByLabelText("Email"), "ana@x.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "secreto1");
    const boton = screen.getByRole("button", { name: "Ingresar" });
    await userEvent.click(boton);
    expect(screen.getByRole("button", { name: "Ingresando…" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Ingresando…" }));
    expect(iniciarSesion).toHaveBeenCalledTimes(1);
    resolver();
    await waitFor(() => expect(screen.getByRole("button", { name: "Ingresar" })).toBeEnabled());
  });
});
```

- [ ] **Step 2: Pruebas de `CuentaSinAcceso` y `CompletarRegistro`**

```jsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { ContextoSesion } from "../sesion/useSesion.js";
import CompletarRegistro from "./CompletarRegistro.jsx";
import CuentaSinAcceso from "./CuentaSinAcceso.jsx";

const base = { aviso: null, recargar: vi.fn(), cerrarSesion: vi.fn(), completarRegistro: vi.fn().mockResolvedValue(undefined) };
const montar = (pantalla, valor) =>
  render(<ContextoSesion.Provider value={{ ...base, ...valor }}>{pantalla}</ContextoSesion.Provider>);

describe("CuentaSinAcceso", () => {
  test("PENDIENTE: muestra 'Esperando activación' y permite actualizar y salir", async () => {
    const recargar = vi.fn();
    const cerrarSesion = vi.fn();
    montar(<CuentaSinAcceso />, { estado: "pendiente", usuario: { nombre: "Ana", email: "ana@x.com" }, recargar, cerrarSesion });
    expect(screen.getByRole("heading", { name: "Esperando activación" })).toBeVisible();
    expect(screen.getByText(/Un coordinador tiene que activar tu cuenta/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Actualizar" }));
    await userEvent.click(screen.getByRole("button", { name: "Cerrar sesión" }));
    expect(recargar).toHaveBeenCalled();
    expect(cerrarSesion).toHaveBeenCalled();
  });

  test("BAJA: avisa que la cuenta está dada de baja", () => {
    montar(<CuentaSinAcceso />, { estado: "baja", usuario: { nombre: "Ana", email: "ana@x.com" } });
    expect(screen.getByRole("heading", { name: "Cuenta dada de baja" })).toBeVisible();
  });
});

describe("CompletarRegistro", () => {
  test("muestra el aviso del registro fallido y manda nombre y código", async () => {
    const completarRegistro = vi.fn().mockResolvedValue(undefined);
    montar(<CompletarRegistro />, { estado: "sin-registro", aviso: "El código de coordinación no es correcto.", completarRegistro });
    expect(screen.getByRole("alert")).toHaveTextContent("El código de coordinación no es correcto.");
    await userEvent.type(screen.getByLabelText("Nombre"), "Ana");
    await userEvent.click(screen.getByRole("button", { name: "Completar registro" }));
    expect(completarRegistro).toHaveBeenCalledWith({ nombre: "Ana", codigo: "" });
  });

  test("muestra el error si el segundo intento también falla", async () => {
    montar(<CompletarRegistro />, { estado: "sin-registro", completarRegistro: vi.fn().mockRejectedValue(new Error("El código de coordinación no es correcto.")) });
    await userEvent.type(screen.getByLabelText("Nombre"), "Ana");
    await userEvent.type(screen.getByLabelText("Código de coordinación (opcional)"), "MAL");
    await userEvent.click(screen.getByRole("button", { name: "Completar registro" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El código de coordinación no es correcto.");
  });
});
```

- [ ] **Step 3: Ver que falla** (`npx vitest run src/pantallas` → faltan los módulos).

- [ ] **Step 4: Implementar `Cargando.jsx`**

```jsx
export default function Cargando({ texto = "Cargando…" }) {
  return (
    <p className="cargando" role="status">
      {texto}
    </p>
  );
}
```

- [ ] **Step 5: Implementar `Acceso.jsx`**

Un hook interno `useEnvio(funcion)` maneja `enviando` y `error` para los tres formularios; se define en este archivo y se exporta para `CompletarRegistro`.

```jsx
import { useState } from "react";
import { useSesion } from "../sesion/useSesion.js";

export function useEnvio(accion) {
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);
  async function enviar(evento) {
    evento.preventDefault();
    if (enviando) return;
    setEnviando(true);
    setError(null);
    try {
      await accion();
    } catch (e) {
      setError(e.message);
    } finally {
      setEnviando(false);
    }
  }
  return { enviando, error, enviar };
}

export default function Acceso() {
  const { iniciarSesion, registrarse, aviso } = useSesion();
  const [modo, setModo] = useState("ingresar");
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [codigo, setCodigo] = useState("");

  const ingreso = modo === "ingresar";
  const { enviando, error, enviar } = useEnvio(() =>
    ingreso ? iniciarSesion(email.trim(), password) : registrarse({ nombre, email: email.trim(), password, codigo }),
  );

  return (
    <main className="acceso">
      <h1>Guardia Viva</h1>
      <div role="tablist" className="pestanas">
        <button role="tab" aria-selected={ingreso} onClick={() => setModo("ingresar")} type="button">Ingresar</button>
        <button role="tab" aria-selected={!ingreso} onClick={() => setModo("registrar")} type="button">Registrarme</button>
      </div>
      {aviso && <p role="status" className="aviso">{aviso}</p>}
      <form onSubmit={enviar}>
        {!ingreso && (
          <label>
            Nombre
            <input value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="name" required maxLength={120} />
          </label>
        )}
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={ingreso ? "current-password" : "new-password"}
            required
            minLength={ingreso ? undefined : 6}
          />
        </label>
        {!ingreso && (
          <label>
            Código de coordinación (opcional)
            <input value={codigo} onChange={(e) => setCodigo(e.target.value)} autoComplete="off" maxLength={64} />
            <small>Solo para coordinadores. Si no lo tenés, dejalo vacío: un coordinador va a activar tu cuenta.</small>
          </label>
        )}
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit" disabled={enviando}>
          {ingreso ? (enviando ? "Ingresando…" : "Ingresar") : enviando ? "Creando cuenta…" : "Crear cuenta"}
        </button>
      </form>
    </main>
  );
}
```

Nota para la prueba "doble clic": el botón con texto "Ingresando…" tiene nombre accesible distinto al de la pestaña "Ingresar"; `getByRole("button", {name:"Ingresar"})` coincide solo con el botón de envío porque las pestañas tienen `role="tab"`.

- [ ] **Step 6: Implementar `CompletarRegistro.jsx`**

```jsx
import { useState } from "react";
import { useSesion } from "../sesion/useSesion.js";
import { useEnvio } from "./Acceso.jsx";

export default function CompletarRegistro() {
  const { completarRegistro, cerrarSesion, aviso } = useSesion();
  const [nombre, setNombre] = useState("");
  const [codigo, setCodigo] = useState("");
  const { enviando, error, enviar } = useEnvio(() => completarRegistro({ nombre, codigo }));
  const mensaje = error ?? aviso;

  return (
    <main className="acceso">
      <h1>Completá tu registro</h1>
      <p>Tu cuenta de ingreso existe, pero falta terminar el registro en Guardia Viva.</p>
      <form onSubmit={enviar}>
        <label>
          Nombre
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="name" required maxLength={120} />
        </label>
        <label>
          Código de coordinación (opcional)
          <input value={codigo} onChange={(e) => setCodigo(e.target.value)} autoComplete="off" maxLength={64} />
        </label>
        {mensaje && <p role="alert" className="error">{mensaje}</p>}
        <button type="submit" disabled={enviando}>{enviando ? "Enviando…" : "Completar registro"}</button>
      </form>
      <button type="button" className="secundario" onClick={cerrarSesion}>Cerrar sesión</button>
    </main>
  );
}
```

- [ ] **Step 7: Implementar `CuentaSinAcceso.jsx`**

```jsx
import { useSesion } from "../sesion/useSesion.js";

export default function CuentaSinAcceso() {
  const { estado, usuario, recargar, cerrarSesion } = useSesion();
  const pendiente = estado === "pendiente";
  return (
    <main className="acceso">
      <h1>{pendiente ? "Esperando activación" : "Cuenta dada de baja"}</h1>
      <p>
        {pendiente
          ? "Un coordinador tiene que activar tu cuenta antes de que puedas ver las guardias."
          : "Tu cuenta ya no tiene acceso. Si es un error, hablá con un coordinador."}
      </p>
      {usuario && <p className="chico">Ingresaste como {usuario.nombre} ({usuario.email}).</p>}
      <div className="acciones">
        {pendiente && <button type="button" onClick={recargar}>Actualizar</button>}
        <button type="button" className="secundario" onClick={cerrarSesion}>Cerrar sesión</button>
      </div>
    </main>
  );
}
```

- [ ] **Step 8: Estilos base `frontend/src/estilos.css`** (variables, formularios, pestañas, aviso/error; la grilla del calendario se agrega en la Tarea 7)

```css
:root {
  --fondo: #faf9f5;
  --texto: #141413;
  --suave: #6b6a65;
  --borde: #dedcd3;
  --primario: #1f5f8b;
  --sobre-primario: #fff;
  --ok: #2e7d4f;
  --ok-fondo: #e6f3ea;
  --alerta: #b26a00;
  --alerta-fondo: #fff1d6;
  --peligro: #b3261e;
  --peligro-fondo: #fde8e6;
  --tarjeta: #fff;
  font: 16px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--texto);
  background: var(--fondo);
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--fondo); }
h1 { font-size: 1.5rem; margin: 0 0 1rem; }
button { font: inherit; min-height: 44px; padding: 0 1rem; border-radius: 8px; border: 1px solid var(--primario); background: var(--primario); color: var(--sobre-primario); cursor: pointer; }
button:disabled { opacity: 0.6; cursor: default; }
button.secundario { background: transparent; color: var(--primario); }
input, textarea { font: inherit; width: 100%; min-height: 44px; padding: 0.5rem 0.75rem; border: 1px solid var(--borde); border-radius: 8px; background: #fff; color: var(--texto); }
label { display: block; margin-bottom: 1rem; font-weight: 600; }
label small { display: block; font-weight: 400; color: var(--suave); margin-top: 0.25rem; }
.acceso { max-width: 420px; margin: 0 auto; padding: 2rem 16px; }
.pestanas { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.pestanas button { flex: 1; background: transparent; color: var(--primario); }
.pestanas button[aria-selected="true"] { background: var(--primario); color: var(--sobre-primario); }
.aviso { background: var(--alerta-fondo); color: var(--alerta); padding: 0.75rem; border-radius: 8px; }
.error { background: var(--peligro-fondo); color: var(--peligro); padding: 0.75rem; border-radius: 8px; }
.chico { color: var(--suave); font-size: 0.875rem; }
.acciones { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.cargando { text-align: center; color: var(--suave); padding: 2rem 16px; }
```

- [ ] **Step 9: Ver que pasa** (`npx vitest run src/pantallas` → PASS).

- [ ] **Step 10: Commit**

```bash
git add src/pantallas src/componentes/Cargando.jsx src/estilos.css
git commit -m "Frontend: pantallas de login, registro con código opcional y espera de activación (D06, D30)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `App` elige la pantalla según el estado de la sesión

**Files:**
- Modify: `frontend/src/main.jsx`, `frontend/src/App.jsx`, `frontend/index.html`
- Create: `frontend/src/pantallas/Calendario.jsx` (marcador mínimo que la Tarea 7 reemplaza; se crea acá solo para que `App` compile)
- Test: `frontend/src/App.test.jsx`

**Interfaces:**
- Consumes: `useSesion()` (estado), pantallas de la Tarea 5.
- Produces: `<App />` (sin props). Tabla: `cargando` → `<Cargando />`; `anonimo` → `<Acceso />`; `sin-registro` → `<CompletarRegistro />`; `pendiente`/`baja` → `<CuentaSinAcceso />`; `activo` → `<Calendario />`; `error` → mensaje con "Reintentar" (`recargar`) y "Cerrar sesión".

- [ ] **Step 1: Prueba**

```jsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import App from "./App.jsx";
import { ContextoSesion } from "./sesion/useSesion.js";

vi.mock("./pantallas/Calendario.jsx", () => ({ default: () => <p>CALENDARIO</p> }));

const montar = (valor) =>
  render(
    <ContextoSesion.Provider value={{ usuario: null, aviso: null, recargar: vi.fn(), cerrarSesion: vi.fn(), ...valor }}>
      <App />
    </ContextoSesion.Provider>,
  );

describe("App", () => {
  test.each([
    ["cargando", /Cargando/],
    ["anonimo", /Guardia Viva/],
    ["sin-registro", /Completá tu registro/],
    ["pendiente", /Esperando activación/],
    ["baja", /Cuenta dada de baja/],
    ["activo", /CALENDARIO/],
  ])("estado %s", (estado, texto) => {
    montar({ estado, aviso: null, iniciarSesion: vi.fn(), registrarse: vi.fn(), completarRegistro: vi.fn() });
    expect(screen.getByText(texto, { selector: "h1, p" })).toBeInTheDocument();
  });

  test("error: muestra el aviso y permite reintentar", async () => {
    const recargar = vi.fn();
    montar({ estado: "error", aviso: "No se pudo conectar con el servidor.", recargar });
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo conectar con el servidor.");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(recargar).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Ver que falla** (`npx vitest run src/App.test.jsx`).

- [ ] **Step 3: Implementar**

`frontend/src/pantallas/Calendario.jsx` (marcador):

```jsx
export default function Calendario() {
  return <p>Calendario</p>;
}
```

`frontend/src/App.jsx`:

```jsx
import Cargando from "./componentes/Cargando.jsx";
import Acceso from "./pantallas/Acceso.jsx";
import Calendario from "./pantallas/Calendario.jsx";
import CompletarRegistro from "./pantallas/CompletarRegistro.jsx";
import CuentaSinAcceso from "./pantallas/CuentaSinAcceso.jsx";
import { useSesion } from "./sesion/useSesion.js";

export default function App() {
  const { estado, aviso, recargar, cerrarSesion } = useSesion();
  switch (estado) {
    case "cargando":
      return <Cargando />;
    case "anonimo":
      return <Acceso />;
    case "sin-registro":
      return <CompletarRegistro />;
    case "pendiente":
    case "baja":
      return <CuentaSinAcceso />;
    case "activo":
      return <Calendario />;
    default:
      return (
        <main className="acceso">
          <h1>Guardia Viva</h1>
          <p role="alert" className="error">{aviso ?? "No se pudo cargar tu cuenta."}</p>
          <div className="acciones">
            <button type="button" onClick={recargar}>Reintentar</button>
            <button type="button" className="secundario" onClick={cerrarSesion}>Cerrar sesión</button>
          </div>
        </main>
      );
  }
}
```

`frontend/src/main.jsx`:

```jsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { crearAuthSupabase } from "./lib/supabase.js";
import { SesionProvider } from "./sesion/SesionProvider.jsx";
import "./estilos.css";

function raiz() {
  try {
    const auth = crearAuthSupabase();
    return (
      <SesionProvider auth={auth}>
        <App />
      </SesionProvider>
    );
  } catch (error) {
    return <p role="alert" className="error">{error.message}</p>;
  }
}

createRoot(document.getElementById("root")).render(<StrictMode>{raiz()}</StrictMode>);
```

`frontend/index.html`: agregar dentro de `<head>`, después del viewport, `<meta name="theme-color" content="#1f5f8b" />`.

- [ ] **Step 4: Ver que pasa** (`npx vitest run` → todo PASS) y `npm run build`.

- [ ] **Step 5: Commit**

```bash
git add src/App.jsx src/App.test.jsx src/main.jsx src/pantallas/Calendario.jsx index.html
git commit -m "Frontend: la app elige la pantalla según el estado de la cuenta (D06, D30)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Calendario semanal con `GET /api/turnos`

**Files:**
- Modify: `frontend/src/pantallas/Calendario.jsx` (reemplaza el marcador), `frontend/src/estilos.css`
- Create: `frontend/src/componentes/TarjetaTurno.jsx`, `frontend/src/pantallas/useTurnosSemana.js`
- Test: `frontend/src/pantallas/useTurnosSemana.test.jsx`, `frontend/src/pantallas/Calendario.test.jsx`, `frontend/src/componentes/TarjetaTurno.test.jsx`

**Interfaces:**
- Consumes: `useSesion()` → `api`, `usuario`, `recargar`, `cerrarSesion`; `fechas.js` (Task 3).
- Produces:
  - `useTurnosSemana(api, lunes, { alCuentaCambiada }) → { estado: "cargando"|"ok"|"error", turnos: TurnoApi[], error: ErrorApi|null, reintentar() }`. Pide `GET /api/turnos?desde=<lunes>&hasta=<domingo>`. Ignora respuestas de una semana que ya no es la visible. Si el error es 403 `CUENTA_PENDIENTE` o `CUENTA_DADA_DE_BAJA` llama a `alCuentaCambiada()`.
  - `TurnoApi = { id: "horarioId:fecha", horarioId, fecha, inicio, fin, duracionHoras, titular: {id, nombre} | null }`.
  - `<TarjetaTurno turno usuario ahora estado onAbrir />` donde `estado` es lo que devuelve `derivarEstado` (Tarea 8); en esta tarea `Calendario` pasa `estado = null` y la tarjeta lo tolera.
  - `ahora`: string ISO del campo `ahora` de `GET /api/health` (o `new Date().toISOString()` si falla), obtenido una vez al montar.
  - Mínimo en `Calendario`: encabezado con `etiquetaSemana`, botones "Semana anterior", "Hoy", "Semana siguiente", lista de días con `data-fecha`, y turnos con `data-testid="turno"` y `data-turno-id`.

- [ ] **Step 1: Pruebas de `TarjetaTurno`**

```jsx
import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import TarjetaTurno from "./TarjetaTurno.jsx";

const turno = {
  id: "7:2026-10-10", horarioId: 7, fecha: "2026-10-10",
  inicio: "2026-10-10T08:00:00-03:00", fin: "2026-10-10T16:00:00-03:00", duracionHoras: 8,
  titular: { id: 3, nombre: "Carlos Ruiz" },
};
const usuario = { id: 1, nombre: "Ana", rol: "MEDICO" };

describe("TarjetaTurno", () => {
  test("muestra horario, duración y titular", () => {
    render(<TarjetaTurno turno={turno} usuario={usuario} estado={null} onAbrir={vi.fn()} />);
    expect(screen.getByText("08:00 – 16:00")).toBeVisible();
    expect(screen.getByText("8 h")).toBeVisible();
    expect(screen.getByText("Carlos Ruiz")).toBeVisible();
  });

  test("marca 'Mi guardia' cuando el titular soy yo", () => {
    render(<TarjetaTurno turno={{ ...turno, titular: { id: 1, nombre: "Ana" } }} usuario={usuario} estado={null} onAbrir={vi.fn()} />);
    expect(screen.getByText("Mi guardia")).toBeVisible();
  });

  test("turno que termina otro día: indica el día siguiente", () => {
    const nocturno = { ...turno, inicio: "2026-10-10T20:00:00-03:00", fin: "2026-10-11T08:00:00-03:00", duracionHoras: 12 };
    render(<TarjetaTurno turno={nocturno} usuario={usuario} estado={null} onAbrir={vi.fn()} />);
    expect(screen.getByText("20:00 – 08:00 (+1 día)")).toBeVisible();
  });

  test("24 horas: termina a la misma hora del día siguiente", () => {
    const largo = { ...turno, inicio: "2026-10-10T08:00:00-03:00", fin: "2026-10-11T08:00:00-03:00", duracionHoras: 24 };
    render(<TarjetaTurno turno={largo} usuario={usuario} estado={null} onAbrir={vi.fn()} />);
    expect(screen.getByText("08:00 – 08:00 (+1 día)")).toBeVisible();
  });

  test("titular null: etiqueta BAJA (D24), sin romper", () => {
    render(<TarjetaTurno turno={{ ...turno, titular: null }} usuario={usuario} estado={null} onAbrir={vi.fn()} />);
    expect(screen.getByText("BAJA")).toBeVisible();
    expect(screen.getByText("Sin titular")).toBeVisible();
  });

  test("clic abre el detalle con el turno", async () => {
    const onAbrir = vi.fn();
    render(<TarjetaTurno turno={turno} usuario={usuario} estado={null} onAbrir={onAbrir} />);
    screen.getByRole("button").click();
    expect(onAbrir).toHaveBeenCalledWith(turno);
  });
});
```

- [ ] **Step 2: Implementar `TarjetaTurno.jsx`**

Etiqueta de "+1 día" se decide comparando `fechaLocal(fin)` con `turno.fecha`. `estado` (Tarea 8) puede traer `{ tipo, etiqueta, urgente }`; si es `null`, no muestra insignia salvo BAJA (que sale de `titular === null`).

```jsx
import { fechaLocal, horaLocal } from "../lib/fechas.js";

export default function TarjetaTurno({ turno, usuario, estado, onAbrir }) {
  const sinTitular = turno.titular === null;
  const mia = !sinTitular && turno.titular.id === usuario.id;
  const diaSiguiente = fechaLocal(turno.fin) !== turno.fecha;
  const horario = `${horaLocal(turno.inicio)} – ${horaLocal(turno.fin)}${diaSiguiente ? " (+1 día)" : ""}`;
  const clases = ["turno", mia && "mio", sinTitular && "baja", estado?.tipo === "VACANTE" && "vacante"].filter(Boolean).join(" ");

  return (
    <button type="button" className={clases} data-testid="turno" data-turno-id={turno.id} onClick={() => onAbrir(turno)}>
      <span className="turno-horario">{horario}</span>
      <span className="turno-duracion">{turno.duracionHoras} h</span>
      <span className="turno-titular">{sinTitular ? "Sin titular" : turno.titular.nombre}</span>
      <span className="insignias">
        {mia && <span className="insignia mia">Mi guardia</span>}
        {sinTitular && <span className="insignia baja">BAJA</span>}
        {estado?.etiqueta && <span className={`insignia ${estado.urgente ? "urgente" : "vacante"}`}>{estado.etiqueta}</span>}
      </span>
    </button>
  );
}
```

- [ ] **Step 3: Pruebas de `useTurnosSemana`**

```jsx
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import { useTurnosSemana } from "./useTurnosSemana.js";

describe("useTurnosSemana", () => {
  test("pide lunes a domingo y devuelve los turnos", async () => {
    const api = { get: vi.fn().mockResolvedValue([{ id: "1:2026-10-05" }]) };
    const { result } = renderHook(() => useTurnosSemana(api, "2026-10-05", { alCuentaCambiada: vi.fn() }));
    expect(result.current.estado).toBe("cargando");
    await waitFor(() => expect(result.current.estado).toBe("ok"));
    expect(api.get).toHaveBeenCalledWith("/api/turnos", { desde: "2026-10-05", hasta: "2026-10-11" });
    expect(result.current.turnos).toEqual([{ id: "1:2026-10-05" }]);
  });

  test("una respuesta vieja no pisa la semana actual", async () => {
    let resolverVieja;
    const api = {
      get: vi.fn((ruta, { desde }) =>
        desde === "2026-10-05" ? new Promise((r) => { resolverVieja = r; }) : Promise.resolve([{ id: "nueva" }]),
      ),
    };
    const { result, rerender } = renderHook(({ lunes }) => useTurnosSemana(api, lunes, { alCuentaCambiada: vi.fn() }), {
      initialProps: { lunes: "2026-10-05" },
    });
    rerender({ lunes: "2026-10-12" });
    await waitFor(() => expect(result.current.turnos).toEqual([{ id: "nueva" }]));
    await act(async () => resolverVieja([{ id: "vieja" }]));
    expect(result.current.turnos).toEqual([{ id: "nueva" }]);
  });

  test("error: estado error y reintentar vuelve a pedir", async () => {
    const api = { get: vi.fn().mockRejectedValueOnce(new ErrorApi(0, "SIN_CONEXION", "Sin conexión.")).mockResolvedValue([]) };
    const { result } = renderHook(() => useTurnosSemana(api, "2026-10-05", { alCuentaCambiada: vi.fn() }));
    await waitFor(() => expect(result.current.estado).toBe("error"));
    expect(result.current.error.message).toBe("Sin conexión.");
    act(() => result.current.reintentar());
    await waitFor(() => expect(result.current.estado).toBe("ok"));
  });

  test.each(["CUENTA_PENDIENTE", "CUENTA_DADA_DE_BAJA"])("403 %s avisa que la cuenta cambió", async (codigo) => {
    const alCuentaCambiada = vi.fn();
    const api = { get: vi.fn().mockRejectedValue(new ErrorApi(403, codigo, "x")) };
    renderHook(() => useTurnosSemana(api, "2026-10-05", { alCuentaCambiada }));
    await waitFor(() => expect(alCuentaCambiada).toHaveBeenCalledTimes(1));
  });
});
```

- [ ] **Step 4: Implementar `useTurnosSemana.js`**

```js
import { useCallback, useEffect, useState } from "react";
import { ErrorApi } from "../lib/api.js";
import { rangoSemana } from "../lib/fechas.js";

const CUENTA_CAMBIADA = ["CUENTA_PENDIENTE", "CUENTA_DADA_DE_BAJA"];

export function useTurnosSemana(api, lunes, { alCuentaCambiada }) {
  const [resultado, setResultado] = useState({ estado: "cargando", turnos: [], error: null });
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    let vigente = true; // si cambia la semana o se desmonta, la respuesta se descarta
    setResultado((previo) => ({ ...previo, estado: "cargando", error: null }));
    api
      .get("/api/turnos", rangoSemana(lunes))
      .then((turnos) => vigente && setResultado({ estado: "ok", turnos, error: null }))
      .catch((error) => {
        if (!vigente) return;
        if (error instanceof ErrorApi && CUENTA_CAMBIADA.includes(error.codigo)) alCuentaCambiada();
        setResultado({ estado: "error", turnos: [], error });
      });
    return () => {
      vigente = false;
    };
    // alCuentaCambiada es estable en la app (recargar de la sesión); no debe re-disparar el pedido.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, lunes, intento]);

  const reintentar = useCallback(() => setIntento((n) => n + 1), []);
  return { ...resultado, reintentar };
}
```

- [ ] **Step 5: Pruebas de `Calendario`**

La prueba mockea `useSesion` con un `api` falso: `get("/api/health")` → `{ahora}` y `get("/api/turnos", {desde, hasta})` → según la semana. Se usa `ContextoSesion.Provider`.

```jsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { ContextoSesion } from "../sesion/useSesion.js";
import Calendario from "./Calendario.jsx";

const turno = (horarioId, fecha, hi, hf, titular, finFecha = fecha) => ({
  id: `${horarioId}:${fecha}`, horarioId, fecha,
  inicio: `${fecha}T${hi}:00-03:00`, fin: `${finFecha}T${hf}:00-03:00`, duracionHoras: 8, titular,
});
const SEMANA_ACTUAL = [
  turno(1, "2026-10-05", "08:00", "16:00", { id: 1, nombre: "Ana" }),
  turno(2, "2026-10-07", "20:00", "08:00", { id: 3, nombre: "Carlos" }, "2026-10-08"),
  turno(3, "2026-10-11", "20:00", "08:00", null, "2026-10-12"),
];

function montar({ turnosPorDesde = {}, health = { ahora: "2026-10-07T10:00:00-03:00" }, usuario = { id: 1, nombre: "Ana", rol: "MEDICO", estado: "ACTIVO" } } = {}) {
  const api = {
    get: vi.fn(async (ruta, consulta) => {
      if (ruta === "/api/health") {
        if (health instanceof Error) throw health;
        return health;
      }
      return turnosPorDesde[consulta.desde] ?? [];
    }),
  };
  render(
    <ContextoSesion.Provider value={{ api, usuario, estado: "activo", recargar: vi.fn(), cerrarSesion: vi.fn() }}>
      <Calendario />
    </ContextoSesion.Provider>,
  );
  return api;
}

describe("Calendario", () => {
  test("arranca en la semana de 'ahora' del servidor (lunes a domingo) y muestra los turnos en su día", async () => {
    const api = montar({ turnosPorDesde: { "2026-10-05": SEMANA_ACTUAL } });
    expect(await screen.findByText("5 al 11 de octubre de 2026")).toBeVisible();
    expect(api.get).toHaveBeenCalledWith("/api/turnos", { desde: "2026-10-05", hasta: "2026-10-11" });
    const dias = document.querySelectorAll("[data-fecha]");
    expect(dias).toHaveLength(7);
    expect(within(document.querySelector('[data-fecha="2026-10-05"]')).getAllByTestId("turno")).toHaveLength(1);
    expect(within(document.querySelector('[data-fecha="2026-10-07"]')).getByText("20:00 – 08:00 (+1 día)")).toBeVisible();
    expect(within(document.querySelector('[data-fecha="2026-10-11"]')).getByText("BAJA")).toBeVisible();
  });

  test("resalta el día de hoy según el servidor", async () => {
    montar({ turnosPorDesde: { "2026-10-05": SEMANA_ACTUAL } });
    await screen.findByText("5 al 11 de octubre de 2026");
    expect(document.querySelector('[data-fecha="2026-10-07"]')).toHaveAttribute("aria-current", "date");
  });

  test("si /health falla, usa la hora del navegador y sigue andando", async () => {
    montar({ health: new Error("caído") });
    expect(await screen.findByRole("heading", { level: 2 })).toBeVisible();
  });

  test("navega a la semana siguiente, a la anterior y vuelve a hoy", async () => {
    const api = montar({ turnosPorDesde: { "2026-10-12": [turno(9, "2026-10-12", "08:00", "14:00", { id: 3, nombre: "Carlos" })] } });
    await screen.findByText("5 al 11 de octubre de 2026");
    await userEvent.click(screen.getByRole("button", { name: "Semana siguiente" }));
    expect(await screen.findByText("12 al 18 de octubre de 2026")).toBeVisible();
    expect(api.get).toHaveBeenCalledWith("/api/turnos", { desde: "2026-10-12", hasta: "2026-10-18" });
    expect(await screen.findByText("Carlos")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Hoy" }));
    expect(await screen.findByText("5 al 11 de octubre de 2026")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Semana anterior" }));
    expect(await screen.findByText("28 de septiembre al 4 de octubre de 2026")).toBeVisible();
  });

  test("semana sin turnos: estado vacío", async () => {
    montar();
    expect(await screen.findByText("No hay guardias esta semana.")).toBeVisible();
  });

  test("error del servidor: mensaje y Reintentar", async () => {
    const api = montar();
    await screen.findByText("5 al 11 de octubre de 2026");
    api.get.mockRejectedValueOnce(Object.assign(new Error("No se pudo conectar con el servidor."), { codigo: "SIN_CONEXION" }));
    await userEvent.click(screen.getByRole("button", { name: "Semana siguiente" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo conectar con el servidor.");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("No hay guardias esta semana.")).toBeVisible();
  });

  test("el coordinador ve el calendario sin acciones de médico", async () => {
    montar({ usuario: { id: 9, nombre: "Enzo", rol: "COORDINADOR", estado: "ACTIVO" }, turnosPorDesde: { "2026-10-05": SEMANA_ACTUAL } });
    expect(await screen.findByText(/pantallas de coordinación/i)).toBeVisible();
  });

  test("cerrar sesión", async () => {
    const cerrarSesion = vi.fn();
    render(
      <ContextoSesion.Provider value={{ api: { get: vi.fn().mockResolvedValue([]) }, usuario: { id: 1, nombre: "Ana", rol: "MEDICO" }, estado: "activo", recargar: vi.fn(), cerrarSesion }}>
        <Calendario />
      </ContextoSesion.Provider>,
    );
    await userEvent.click(await screen.findByRole("button", { name: "Cerrar sesión" }));
    expect(cerrarSesion).toHaveBeenCalled();
  });
});
```

(En esta tarea `Calendario` aún no usa `derivarEstado`; las pruebas de "coordinador" y de acciones del detalle se completan en la Tarea 8. La prueba del coordinador queda acá porque el aviso pertenece al calendario.)

- [ ] **Step 6: Implementar `Calendario.jsx`**

El detalle (`DetalleTurno`) se agrega en la Tarea 8; acá `onAbrir` solo guarda el turno seleccionado en estado y no renderiza nada más.

```jsx
import { useEffect, useMemo, useState } from "react";
import Cargando from "../componentes/Cargando.jsx";
import TarjetaTurno from "../componentes/TarjetaTurno.jsx";
import {
  agruparPorDia, diasDeSemana, etiquetaDia, etiquetaSemana, fechaLocal, lunesDe, sumarDias,
} from "../lib/fechas.js";
import { useSesion } from "../sesion/useSesion.js";
import { useTurnosSemana } from "./useTurnosSemana.js";

export default function Calendario() {
  const { api, usuario, recargar, cerrarSesion } = useSesion();
  const [ahora, setAhora] = useState(null);
  const [lunes, setLunes] = useState(null);
  const [, setSeleccionado] = useState(null);

  // "Hoy" sale del reloj del servidor (D27): el reloj de demo también mueve el calendario.
  useEffect(() => {
    let vigente = true;
    api
      .get("/api/health")
      .then((salud) => salud.ahora)
      .catch(() => new Date().toISOString())
      .then((instante) => {
        if (!vigente) return;
        setAhora(instante);
        setLunes(lunesDe(fechaLocal(instante)));
      });
    return () => {
      vigente = false;
    };
  }, [api]);

  if (lunes === null) return <Cargando texto="Cargando el calendario…" />;
  return <Semana api={api} usuario={usuario} ahora={ahora} lunes={lunes} setLunes={setLunes} setSeleccionado={setSeleccionado} recargar={recargar} cerrarSesion={cerrarSesion} />;
}

function Semana({ api, usuario, ahora, lunes, setLunes, setSeleccionado, recargar, cerrarSesion }) {
  const { estado, turnos, error, reintentar } = useTurnosSemana(api, lunes, { alCuentaCambiada: recargar });
  const dias = useMemo(() => diasDeSemana(lunes), [lunes]);
  const porDia = useMemo(() => agruparPorDia(turnos, dias), [turnos, dias]);
  const hoy = fechaLocal(ahora);
  const esCoordinador = usuario.rol === "COORDINADOR";

  return (
    <main className="calendario">
      <header className="cabecera">
        <div>
          <h2>{etiquetaSemana(lunes)}</h2>
          <p className="chico">{usuario.nombre}</p>
        </div>
        <button type="button" className="secundario" onClick={cerrarSesion}>Cerrar sesión</button>
      </header>
      <nav className="navegacion" aria-label="Semana">
        <button type="button" onClick={() => setLunes(sumarDias(lunes, -7))}>Semana anterior</button>
        <button type="button" className="secundario" onClick={() => setLunes(lunesDe(hoy))}>Hoy</button>
        <button type="button" onClick={() => setLunes(sumarDias(lunes, 7))}>Semana siguiente</button>
      </nav>
      {esCoordinador && <p className="aviso">Ingresaste como coordinador: las pantallas de coordinación se suman más adelante.</p>}
      {estado === "cargando" && <Cargando />}
      {estado === "error" && (
        <div>
          <p role="alert" className="error">{error.message}</p>
          <button type="button" onClick={reintentar}>Reintentar</button>
        </div>
      )}
      {estado === "ok" && turnos.length === 0 && <p className="vacio">No hay guardias esta semana.</p>}
      {estado === "ok" && (
        <div className="semana">
          {dias.map((dia) => (
            <section key={dia} className="dia" data-fecha={dia} aria-current={dia === hoy ? "date" : undefined}>
              <h3>{etiquetaDia(dia)}</h3>
              {porDia[dia].map((turno) => (
                <TarjetaTurno key={turno.id} turno={turno} usuario={usuario} estado={null} onAbrir={setSeleccionado} />
              ))}
            </section>
          ))}
        </div>
      )}
    </main>
  );
}
```

Si la prueba "semana sin turnos" muestra además los 7 días vacíos, es aceptable: la grilla se renderiza igual y el mensaje aclara. Ajustar a gusto, sin quitar el mensaje.

- [ ] **Step 7: Estilos del calendario** (agregar a `estilos.css`)

```css
.calendario { max-width: 1200px; margin: 0 auto; padding: 1rem 16px 3rem; }
.cabecera { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
.cabecera h2 { margin: 0; font-size: 1.25rem; }
.navegacion { display: flex; gap: 0.5rem; margin: 1rem 0; }
.navegacion button { flex: 1; }
.vacio { text-align: center; color: var(--suave); padding: 1rem; }
.semana { display: grid; grid-template-columns: 1fr; gap: 0.75rem; }
.dia { background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 12px; padding: 0.75rem; min-width: 0; }
.dia[aria-current="date"] { border-color: var(--primario); box-shadow: 0 0 0 2px var(--primario) inset; }
.dia h3 { margin: 0 0 0.5rem; font-size: 0.95rem; text-transform: capitalize; }
.turno { display: grid; gap: 0.15rem; width: 100%; text-align: left; min-height: 64px; padding: 0.5rem 0.75rem; margin-bottom: 0.5rem; background: #f3f1ea; color: var(--texto); border: 1px solid var(--borde); }
.turno.mio { background: var(--ok-fondo); border-color: var(--ok); }
.turno.baja { background: var(--peligro-fondo); border-color: var(--peligro); }
.turno.vacante { background: var(--alerta-fondo); border-color: var(--alerta); }
.turno-horario { font-weight: 700; }
.turno-duracion, .turno-titular { font-size: 0.875rem; color: var(--suave); }
.insignias { display: flex; flex-wrap: wrap; gap: 0.25rem; }
.insignia { font-size: 0.75rem; font-weight: 700; padding: 0.1rem 0.5rem; border-radius: 999px; background: #fff; border: 1px solid var(--borde); }
.insignia.mia { color: var(--ok); border-color: var(--ok); }
.insignia.baja, .insignia.urgente { color: var(--peligro); border-color: var(--peligro); }
.insignia.vacante { color: var(--alerta); border-color: var(--alerta); }
@media (min-width: 900px) {
  .semana { grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 0.5rem; }
}
```

- [ ] **Step 8: Ver que pasa** (`npx vitest run` y `npm run build`).

- [ ] **Step 9: Commit**

```bash
git add src/pantallas src/componentes/TarjetaTurno.jsx src/componentes/TarjetaTurno.test.jsx src/estilos.css
git commit -m "Frontend: calendario semanal que consume GET /api/turnos (D09, D13, D24)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Botones de vacantes y postulaciones con datos simulados

**Files:**
- Create: `frontend/src/simulado/vacantes.js`, `frontend/src/simulado/useVacantesSimuladas.js`, `frontend/src/componentes/DetalleTurno.jsx`
- Modify: `frontend/src/pantallas/Calendario.jsx`, `frontend/src/estilos.css`
- Test: `frontend/src/simulado/vacantes.test.js`, `frontend/src/componentes/DetalleTurno.test.jsx`, `frontend/src/pantallas/Calendario.test.jsx` (agregar casos)

**Interfaces:**
- Consumes: `horasHasta`, `terminoAntes` (Task 3); `TarjetaTurno` (`estado` prop).
- Produces:
  - `hashTurno(turnoId) → number` (entero ≥ 0, determinista).
  - `derivarEstado({ turno, usuario, ahora, override }) → Estado`, con
    `override = { vacante?: boolean, motivo?: string, postulado?: boolean } | undefined` y
    `Estado = { tipo: "NORMAL"|"VACANTE"|"BAJA"|"PASADO", etiqueta: string|null, urgente: boolean, postulantes: {id:number,nombre:string}[], postulado: boolean, acciones: ("AVISAR_AUSENCIA"|"RETIRAR_AVISO"|"POSTULARME"|"RETIRAR_POSTULACION")[] }`.
    `etiqueta`: `"Vacante"`, `"Vacante urgente"`, `"BAJA"` o `null`.
  - `useVacantesSimuladas({ usuario, ahora }) → { estadoDe(turno), avisarAusencia(turnoId, motivo), retirarAviso(turnoId), postularme(turnoId), retirarPostulacion(turnoId) }` (overrides en memoria, `useState`).
  - `<DetalleTurno turno estado usuario onCerrar acciones />` con `acciones = { avisarAusencia, retirarAviso, postularme, retirarPostulacion }`; `role="dialog"` con título "Detalle de la guardia", texto "Simulado" visible (`data-testid="rotulo-simulado"`), y botones "Avisar ausencia" (con campo "Motivo (solo lo ven los coordinadores)"), "Retirar aviso", "Postularme", "Retirar postulación" según `estado.acciones`.

**Reglas de `derivarEstado`** (decisión 7):
1. `PASADO`: `terminoAntes(turno, ahora)` → sin acciones, sin etiqueta.
2. Titular `null` → base `BAJA` (etiqueta `"BAJA"`); se trata como vacante abierta cubrible: acciones según la regla de otro médico.
3. Titular soy yo: sin `override.vacante` → `NORMAL`, acciones `["AVISAR_AUSENCIA"]`; con `override.vacante` → `VACANTE`, acciones `["RETIRAR_AVISO"]`.
4. Titular es otro médico: vacante abierta si `hashTurno(turno.id) % 5 === 0`; con postulante simulado `{id: -1, nombre: "Florencia"}` si además `% 10 === 0`. Si hay vacante (o BAJA): acciones `["POSTULARME"]`, o `["RETIRAR_POSTULACION"]` si `override.postulado`; si no hay vacante: sin acciones.
5. `urgente`: hay vacante abierta (incluida BAJA no) y `0 <= horasHasta(turno, ahora) < 24` → etiqueta `"Vacante urgente"`. (La BAJA no es urgente: tiene su propia etiqueta, D24.)
6. `postulantes`: los simulados + el propio usuario si `override.postulado`.
7. Un COORDINADOR: `acciones = []` siempre, aunque el resto del estado se calcule igual.

- [ ] **Step 1: Pruebas de `derivarEstado`**

Para no depender de qué ids caen en `% 5`, la prueba busca un id que cumpla (helper que prueba `horarioId` de 1 a 200).

```js
import { describe, expect, test } from "vitest";
import { derivarEstado, hashTurno } from "./vacantes.js";

const ahora = "2026-10-07T10:00:00-03:00";
const yo = { id: 1, nombre: "Ana", rol: "MEDICO" };
const otro = { id: 3, nombre: "Carlos" };

function turnoCon(titular, { fecha = "2026-10-12", inicio = "08:00", fin = "16:00", horarioId = 5 } = {}) {
  return { id: `${horarioId}:${fecha}`, horarioId, fecha, inicio: `${fecha}T${inicio}:00-03:00`, fin: `${fecha}T${fin}:00-03:00`, duracionHoras: 8, titular };
}
function turnoAjenoConVacante(extra = {}) {
  for (let h = 1; h < 500; h++) {
    const t = turnoCon(otro, { horarioId: h, ...extra });
    if (hashTurno(t.id) % 5 === 0 && hashTurno(t.id) % 10 !== 0) return t;
  }
  throw new Error("sin turno con vacante");
}
function turnoAjenoSinVacante() {
  for (let h = 1; h < 500; h++) {
    const t = turnoCon(otro, { horarioId: h });
    if (hashTurno(t.id) % 5 !== 0) return t;
  }
  throw new Error("sin turno normal");
}
function turnoAjenoConPostulante() {
  for (let h = 1; h < 500; h++) {
    const t = turnoCon(otro, { horarioId: h });
    if (hashTurno(t.id) % 10 === 0) return t;
  }
  throw new Error("sin turno con postulante");
}

describe("hashTurno", () => {
  test("es determinista y no negativo", () => {
    expect(hashTurno("7:2026-10-10")).toBe(hashTurno("7:2026-10-10"));
    expect(hashTurno("7:2026-10-10")).toBeGreaterThanOrEqual(0);
  });
});

describe("derivarEstado", () => {
  test("mi turno futuro: normal, puedo avisar mi ausencia", () => {
    const e = derivarEstado({ turno: turnoCon(yo), usuario: yo, ahora });
    expect(e).toMatchObject({ tipo: "NORMAL", etiqueta: null, acciones: ["AVISAR_AUSENCIA"], urgente: false });
  });

  test("mi turno con aviso abierto: vacante y puedo retirar el aviso", () => {
    const e = derivarEstado({ turno: turnoCon(yo), usuario: yo, ahora, override: { vacante: true, motivo: "Congreso" } });
    expect(e).toMatchObject({ tipo: "VACANTE", etiqueta: "Vacante", acciones: ["RETIRAR_AVISO"] });
  });

  test("nunca puedo postularme a mi propio turno (D16)", () => {
    const e = derivarEstado({ turno: turnoCon(yo), usuario: yo, ahora, override: { vacante: true } });
    expect(e.acciones).not.toContain("POSTULARME");
  });

  test("turno ajeno con vacante simulada: puedo postularme; ya postulado, retirar", () => {
    const t = turnoAjenoConVacante();
    expect(derivarEstado({ turno: t, usuario: yo, ahora })).toMatchObject({ tipo: "VACANTE", acciones: ["POSTULARME"], postulado: false });
    const e = derivarEstado({ turno: t, usuario: yo, ahora, override: { postulado: true } });
    expect(e).toMatchObject({ acciones: ["RETIRAR_POSTULACION"], postulado: true });
    expect(e.postulantes.map((p) => p.id)).toContain(yo.id);
  });

  test("turno ajeno sin vacante: sin acciones", () => {
    expect(derivarEstado({ turno: turnoAjenoSinVacante(), usuario: yo, ahora })).toMatchObject({ tipo: "NORMAL", acciones: [] });
  });

  test("algunos turnos ajenos traen un postulante simulado", () => {
    const e = derivarEstado({ turno: turnoAjenoConPostulante(), usuario: yo, ahora });
    expect(e.postulantes).toEqual([{ id: -1, nombre: "Florencia" }]);
  });

  test("titular null: BAJA, se puede cubrir y no es urgente", () => {
    const e = derivarEstado({ turno: turnoCon(null, { fecha: "2026-10-08" }), usuario: yo, ahora });
    expect(e).toMatchObject({ tipo: "BAJA", etiqueta: "BAJA", urgente: false, acciones: ["POSTULARME"] });
  });

  test("vacante con menos de 24 h de anticipación es urgente (D15)", () => {
    const t = turnoCon(yo, { fecha: "2026-10-07", inicio: "20:00", fin: "23:00", horarioId: 1 });
    const e = derivarEstado({ turno: t, usuario: yo, ahora, override: { vacante: true } });
    expect(e).toMatchObject({ urgente: true, etiqueta: "Vacante urgente" });
  });

  test("vacante con 24 h o más no es urgente", () => {
    const t = turnoCon(yo, { fecha: "2026-10-08", inicio: "10:00", fin: "18:00" });
    expect(derivarEstado({ turno: t, usuario: yo, ahora, override: { vacante: true } }).urgente).toBe(false);
  });

  test("turno ya terminado: PASADO sin acciones", () => {
    const t = turnoCon(yo, { fecha: "2026-10-06" });
    expect(derivarEstado({ turno: t, usuario: yo, ahora })).toMatchObject({ tipo: "PASADO", acciones: [], etiqueta: null });
  });

  test("turno en curso (ya empezó, no terminó) de otro: sin urgencia", () => {
    const t = turnoCon(yo, { fecha: "2026-10-07", inicio: "08:00", fin: "16:00" });
    const e = derivarEstado({ turno: t, usuario: yo, ahora, override: { vacante: true } });
    expect(e.urgente).toBe(false);
  });

  test("el coordinador no tiene acciones", () => {
    const coord = { id: 9, nombre: "Enzo", rol: "COORDINADOR" };
    expect(derivarEstado({ turno: turnoCon(null), usuario: coord, ahora }).acciones).toEqual([]);
  });
});
```

- [ ] **Step 2: Ver que falla**, **implementar `vacantes.js`**

```js
// DATOS SIMULADOS: hasta que existan los endpoints de vacantes y postulaciones (D15, D16), el estado de
// cada turno se deriva acá. Cuando existan, esta carpeta se reemplaza por llamadas a la API.
import { horasHasta, terminoAntes } from "../lib/fechas.js";

const POSTULANTE_SIMULADO = { id: -1, nombre: "Florencia" };

export function hashTurno(turnoId) {
  let h = 0;
  for (let i = 0; i < turnoId.length; i++) h = (h * 31 + turnoId.charCodeAt(i)) >>> 0;
  return h;
}

export function derivarEstado({ turno, usuario, ahora, override }) {
  const sinAcciones = (tipo) => ({ tipo, etiqueta: tipo === "BAJA" ? "BAJA" : null, urgente: false, postulantes: [], postulado: false, acciones: [] });
  if (terminoAntes(turno, ahora)) return sinAcciones("PASADO");

  const esCoordinador = usuario.rol === "COORDINADOR";
  const sinTitular = turno.titular === null;
  const mio = !sinTitular && turno.titular.id === usuario.id;
  const hash = hashTurno(turno.id);

  let vacante;
  if (sinTitular) vacante = true;
  else if (mio) vacante = Boolean(override?.vacante);
  else vacante = hash % 5 === 0;

  const postulado = !mio && Boolean(override?.postulado);
  const postulantes = [];
  if (!mio && !sinTitular && vacante && hash % 10 === 0) postulantes.push(POSTULANTE_SIMULADO);
  if (postulado) postulantes.push({ id: usuario.id, nombre: usuario.nombre });

  const urgente = vacante && !sinTitular && (() => { const h = horasHasta(turno, ahora); return h >= 0 && h < 24; })();

  let acciones = [];
  if (!esCoordinador) {
    if (mio) acciones = [vacante ? "RETIRAR_AVISO" : "AVISAR_AUSENCIA"];
    else if (vacante) acciones = [postulado ? "RETIRAR_POSTULACION" : "POSTULARME"];
  }

  let tipo = "NORMAL";
  let etiqueta = null;
  if (sinTitular) { tipo = "BAJA"; etiqueta = "BAJA"; }
  else if (vacante) { tipo = "VACANTE"; etiqueta = urgente ? "Vacante urgente" : "Vacante"; }

  return { tipo, etiqueta, urgente, postulantes, postulado, acciones };
}
```

- [ ] **Step 3: `useVacantesSimuladas.js`**

```js
import { useCallback, useState } from "react";
import { derivarEstado } from "./vacantes.js";

export function useVacantesSimuladas({ usuario, ahora }) {
  const [overrides, setOverrides] = useState({});
  const cambiar = useCallback((turnoId, parche) => setOverrides((previo) => ({ ...previo, [turnoId]: { ...previo[turnoId], ...parche } })), []);

  return {
    estadoDe: (turno) => derivarEstado({ turno, usuario, ahora, override: overrides[turno.id] }),
    avisarAusencia: (turnoId, motivo) => cambiar(turnoId, { vacante: true, motivo }),
    retirarAviso: (turnoId) => cambiar(turnoId, { vacante: false, motivo: undefined }),
    postularme: (turnoId) => cambiar(turnoId, { postulado: true }),
    retirarPostulacion: (turnoId) => cambiar(turnoId, { postulado: false }),
  };
}
```

- [ ] **Step 4: Pruebas de `DetalleTurno`**

```jsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import DetalleTurno from "./DetalleTurno.jsx";

const turno = {
  id: "7:2026-10-12", horarioId: 7, fecha: "2026-10-12",
  inicio: "2026-10-12T08:00:00-03:00", fin: "2026-10-12T16:00:00-03:00", duracionHoras: 8,
  titular: { id: 3, nombre: "Carlos Ruiz" },
};
const estadoBase = { tipo: "NORMAL", etiqueta: null, urgente: false, postulantes: [], postulado: false, acciones: [] };
const acciones = () => ({ avisarAusencia: vi.fn(), retirarAviso: vi.fn(), postularme: vi.fn(), retirarPostulacion: vi.fn() });
const montar = (estado, acc = acciones(), onCerrar = vi.fn()) => {
  render(<DetalleTurno turno={turno} estado={{ ...estadoBase, ...estado }} acciones={acc} onCerrar={onCerrar} />);
  return { acc, onCerrar };
};

describe("DetalleTurno", () => {
  test("rotula que las acciones son simuladas", () => {
    montar({});
    expect(screen.getByTestId("rotulo-simulado")).toHaveTextContent("Simulado");
  });

  test("Avisar ausencia pide motivo (visible solo para coordinadores) y lo manda", async () => {
    const { acc } = montar({ acciones: ["AVISAR_AUSENCIA"] });
    expect(screen.getByText(/solo lo ven los coordinadores/i)).toBeVisible();
    await userEvent.type(screen.getByLabelText(/Motivo/), "Congreso");
    await userEvent.click(screen.getByRole("button", { name: "Avisar ausencia" }));
    expect(acc.avisarAusencia).toHaveBeenCalledWith("7:2026-10-12", "Congreso");
  });

  test("el motivo es obligatorio", async () => {
    const { acc } = montar({ acciones: ["AVISAR_AUSENCIA"] });
    await userEvent.click(screen.getByRole("button", { name: "Avisar ausencia" }));
    expect(acc.avisarAusencia).not.toHaveBeenCalled();
  });

  test.each([
    ["RETIRAR_AVISO", "Retirar aviso", "retirarAviso"],
    ["POSTULARME", "Postularme", "postularme"],
    ["RETIRAR_POSTULACION", "Retirar postulación", "retirarPostulacion"],
  ])("acción %s", async (accion, texto, funcion) => {
    const { acc } = montar({ acciones: [accion] });
    await userEvent.click(screen.getByRole("button", { name: texto }));
    expect(acc[funcion]).toHaveBeenCalledWith("7:2026-10-12");
  });

  test("sin acciones no hay botones de acción", () => {
    montar({ acciones: [] });
    expect(screen.queryByRole("button", { name: /Avisar|Postularme|Retirar/ })).toBeNull();
  });

  test("lista postulantes y marca urgente", () => {
    montar({ tipo: "VACANTE", etiqueta: "Vacante urgente", urgente: true, postulantes: [{ id: -1, nombre: "Florencia" }] });
    expect(screen.getByText("Florencia")).toBeVisible();
    expect(screen.getByText("Vacante urgente")).toBeVisible();
  });

  test("cerrar", async () => {
    const { onCerrar } = montar({});
    await userEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(onCerrar).toHaveBeenCalled();
  });
});
```

- [ ] **Step 5: Implementar `DetalleTurno.jsx`**

```jsx
import { useState } from "react";
import { etiquetaDia, fechaLocal, horaLocal } from "../lib/fechas.js";

export default function DetalleTurno({ turno, estado, acciones, onCerrar }) {
  const [motivo, setMotivo] = useState("");
  const [intentoSinMotivo, setIntentoSinMotivo] = useState(false);
  const diaSiguiente = fechaLocal(turno.fin) !== turno.fecha;
  const puede = (accion) => estado.acciones.includes(accion);

  function avisar(evento) {
    evento.preventDefault();
    if (!motivo.trim()) {
      setIntentoSinMotivo(true);
      return;
    }
    acciones.avisarAusencia(turno.id, motivo.trim());
    setMotivo("");
  }

  return (
    <div className="detalle-fondo">
      <section className="detalle" role="dialog" aria-modal="true" aria-labelledby="detalle-titulo">
        <h2 id="detalle-titulo">Detalle de la guardia</h2>
        <p data-testid="rotulo-simulado" className="aviso">Simulado: todavía no hay vacantes ni postulaciones en el servidor; lo que hagas acá solo vive en esta pestaña.</p>
        <dl>
          <dt>Día</dt>
          <dd>{etiquetaDia(turno.fecha)}</dd>
          <dt>Horario</dt>
          <dd>{horaLocal(turno.inicio)} – {horaLocal(turno.fin)}{diaSiguiente ? " (+1 día)" : ""} · {turno.duracionHoras} h</dd>
          <dt>Titular</dt>
          <dd>{turno.titular ? turno.titular.nombre : "Sin titular (baja)"}</dd>
          {estado.etiqueta && (<><dt>Estado</dt><dd><strong>{estado.etiqueta}</strong></dd></>)}
        </dl>
        {estado.postulantes.length > 0 && (
          <>
            <h3>Postulantes</h3>
            <ul>{estado.postulantes.map((p) => <li key={p.id}>{p.nombre}</li>)}</ul>
          </>
        )}
        {puede("AVISAR_AUSENCIA") && (
          <form onSubmit={avisar} noValidate>
            <label>
              Motivo (solo lo ven los coordinadores)
              <input value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={500} />
            </label>
            {intentoSinMotivo && !motivo.trim() && <p role="alert" className="error">Escribí el motivo de la ausencia.</p>}
            <button type="submit">Avisar ausencia</button>
          </form>
        )}
        {puede("RETIRAR_AVISO") && <button type="button" onClick={() => acciones.retirarAviso(turno.id)}>Retirar aviso</button>}
        {puede("POSTULARME") && <button type="button" onClick={() => acciones.postularme(turno.id)}>Postularme</button>}
        {puede("RETIRAR_POSTULACION") && <button type="button" onClick={() => acciones.retirarPostulacion(turno.id)}>Retirar postulación</button>}
        <button type="button" className="secundario" onClick={onCerrar}>Cerrar</button>
      </section>
    </div>
  );
}
```

- [ ] **Step 6: Integrar en `Calendario.jsx`**

En `Semana` (el hook `useVacantesSimuladas` se llama en `Semana`, que ya tiene `usuario` y `ahora`): reemplazar `estado={null}` por `estado={simulado.estadoDe(turno)}`; guardar `seleccionado` (turno completo) en `Calendario`/`Semana` y mostrar el detalle con el estado recalculado en cada render:

```jsx
const simulado = useVacantesSimuladas({ usuario, ahora });
const [seleccionado, setSeleccionado] = useState(null);
// ...
{seleccionado && (
  <DetalleTurno turno={seleccionado} estado={simulado.estadoDe(seleccionado)} acciones={simulado} onCerrar={() => setSeleccionado(null)} />
)}
```

(`seleccionado` y `setSeleccionado` pasan a vivir en `Semana`; se quita el `useState` provisorio de `Calendario`.) Si cambia la semana, `setSeleccionado(null)`: agregar `useEffect(() => setSeleccionado(null), [lunes])`.

- [ ] **Step 7: Estilos del detalle** (agregar a `estilos.css`)

```css
.detalle-fondo { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.4); display: flex; align-items: flex-end; justify-content: center; z-index: 10; }
.detalle { background: var(--tarjeta); width: 100%; max-width: 480px; max-height: 90vh; overflow-y: auto; border-radius: 16px 16px 0 0; padding: 1rem 16px 1.5rem; display: grid; gap: 0.75rem; }
.detalle h2, .detalle h3 { margin: 0; }
.detalle dl { display: grid; grid-template-columns: auto 1fr; gap: 0.25rem 1rem; margin: 0; }
.detalle dt { color: var(--suave); }
.detalle dd { margin: 0; }
@media (min-width: 900px) { .detalle-fondo { align-items: center; } .detalle { border-radius: 16px; } }
```

- [ ] **Step 8: Casos nuevos en `Calendario.test.jsx`**

```jsx
test("abrir un turno propio y avisar la ausencia lo marca como vacante (simulado)", async () => {
  montar({ turnosPorDesde: { "2026-10-05": [turno(1, "2026-10-09", "08:00", "16:00", { id: 1, nombre: "Ana" })] } });
  await userEvent.click(await screen.findByTestId("turno"));
  expect(screen.getByTestId("rotulo-simulado")).toBeVisible();
  await userEvent.type(screen.getByLabelText(/Motivo/), "Congreso");
  await userEvent.click(screen.getByRole("button", { name: "Avisar ausencia" }));
  expect(screen.getAllByText("Vacante").length).toBeGreaterThan(0);
  await userEvent.click(screen.getByRole("button", { name: "Retirar aviso" }));
  expect(screen.getByRole("button", { name: "Avisar ausencia" })).toBeVisible();
});

test("el coordinador no ve botones de acción en el detalle", async () => {
  montar({
    usuario: { id: 9, nombre: "Enzo", rol: "COORDINADOR", estado: "ACTIVO" },
    turnosPorDesde: { "2026-10-05": [turno(1, "2026-10-09", "08:00", "16:00", null)] },
  });
  await userEvent.click(await screen.findByTestId("turno"));
  expect(screen.queryByRole("button", { name: /Postularme|Avisar ausencia/ })).toBeNull();
});

test("cambiar de semana cierra el detalle", async () => {
  montar({ turnosPorDesde: { "2026-10-05": [turno(1, "2026-10-09", "08:00", "16:00", { id: 1, nombre: "Ana" })] } });
  await userEvent.click(await screen.findByTestId("turno"));
  await userEvent.click(screen.getByRole("button", { name: "Semana siguiente" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});
```

- [ ] **Step 9: Ver que pasa** (`npx vitest run` y `npm run build`).

- [ ] **Step 10: Commit**

```bash
git add src/simulado src/componentes/DetalleTurno.jsx src/componentes/DetalleTurno.test.jsx src/pantallas src/estilos.css
git commit -m "Frontend: botones de vacantes y postulaciones con datos simulados (D15, D16, D24, D25)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Pruebas e2e con Playwright

**Files:**
- Create: `frontend/e2e/ayudas.js`, `frontend/e2e/medico.spec.js`, `frontend/e2e/contrato.spec.js`
- Delete: `frontend/e2e/health.spec.js`

**Interfaces:**
- Produces (`ayudas.js`): `tokenFalso(email) → string` (JWT con forma válida y firma falsa, `exp` lejano), `simularSupabase(page, { usuarios })` (intercepta `**/auth/v1/**`: `POST /token?grant_type=password` y `POST /signup` devuelven una sesión; `POST /logout` → 204; credenciales distintas de las de `usuarios` → 400 `invalid_credentials`), `simularApi(page, { me, turnos, ahora })` (intercepta `**/api/**`; registra los pedidos en `pedidos[]` con `{metodo, ruta, authorization}`; `me` puede ser un objeto o una función; sin `Authorization: Bearer` responde 401 `SIN_SESION` como el backend real).

- [ ] **Step 1: Escribir `ayudas.js`**

```js
const b64 = (objeto) => Buffer.from(JSON.stringify(objeto)).toString("base64url");

export function tokenFalso(email) {
  const ahora = Math.floor(Date.now() / 1000);
  return `${b64({ alg: "HS256", typ: "JWT" })}.${b64({ sub: `id-${email}`, email, aud: "authenticated", role: "authenticated", iat: ahora, exp: ahora + 3600 })}.firma`;
}

function sesionDe(email) {
  const ahora = Math.floor(Date.now() / 1000);
  return {
    access_token: tokenFalso(email),
    token_type: "bearer",
    expires_in: 3600,
    expires_at: ahora + 3600,
    refresh_token: "refresco",
    user: { id: `id-${email}`, aud: "authenticated", role: "authenticated", email, app_metadata: {}, user_metadata: {}, created_at: "2026-10-01T00:00:00Z" },
  };
}

export async function simularSupabase(page, { usuarios = { "ana@x.com": "secreto1" } } = {}) {
  await page.route("**/auth/v1/**", async (ruta) => {
    const peticion = ruta.request();
    const url = new URL(peticion.url());
    const json = (status, cuerpo) => ruta.fulfill({ status, contentType: "application/json", body: JSON.stringify(cuerpo) });
    if (url.pathname.endsWith("/token")) {
      const { email, password } = peticion.postDataJSON();
      if (usuarios[email] === password) return json(200, sesionDe(email));
      return json(400, { code: "invalid_credentials", error_code: "invalid_credentials", msg: "Invalid login credentials", message: "Invalid login credentials" });
    }
    if (url.pathname.endsWith("/signup")) {
      const { email } = peticion.postDataJSON();
      return json(200, sesionDe(email));
    }
    if (url.pathname.endsWith("/logout")) return ruta.fulfill({ status: 204 });
    return json(404, { message: "no simulado" });
  });
}

export async function simularApi(page, { me, turnos = [], ahora = "2026-10-07T10:00:00-03:00", registro } = {}) {
  const pedidos = [];
  await page.route("**/api/**", async (ruta) => {
    const peticion = ruta.request();
    const url = new URL(peticion.url());
    const authorization = peticion.headers()["authorization"] ?? null;
    pedidos.push({ metodo: peticion.method(), ruta: url.pathname, consulta: url.search, authorization, cuerpo: peticion.postData() });
    const json = (status, cuerpo) => ruta.fulfill({ status, contentType: "application/json", body: JSON.stringify(cuerpo) });
    if (url.pathname === "/api/health") return json(200, { estado: "ok", base: "ok", ahora });
    if (!authorization?.startsWith("Bearer ")) return json(401, { codigo: "SIN_SESION", mensaje: "Falta el token de sesión." });
    if (url.pathname === "/api/me") {
      const valor = typeof me === "function" ? me(pedidos) : me;
      return valor.status ? json(valor.status, valor.cuerpo) : json(200, valor);
    }
    if (url.pathname === "/api/registro") {
      const respuesta = registro ? registro(peticion.postDataJSON()) : { status: 201, cuerpo: me };
      return json(respuesta.status, respuesta.cuerpo);
    }
    if (url.pathname === "/api/turnos") return json(200, typeof turnos === "function" ? turnos(url.searchParams) : turnos);
    return json(404, { codigo: "NO_ENCONTRADO", mensaje: "No existe." });
  });
  return pedidos;
}
```

- [ ] **Step 2: Escribir `medico.spec.js`**

```js
import { expect, test } from "@playwright/test";
import { simularApi, simularSupabase } from "./ayudas.js";

const ME = { id: 1, nombre: "Ana Gómez", email: "ana@x.com", rol: "MEDICO", estado: "ACTIVO" };
const turno = (horarioId, fecha, hi, hf, finFecha, titular) => ({
  id: `${horarioId}:${fecha}`, horarioId, fecha, inicio: `${fecha}T${hi}:00-03:00`, fin: `${finFecha}T${hf}:00-03:00`, duracionHoras: 8, titular,
});
const TURNOS = [
  turno(1, "2026-10-09", "08:00", "16:00", "2026-10-09", { id: 1, nombre: "Ana Gómez" }),
  turno(2, "2026-10-10", "20:00", "08:00", "2026-10-11", { id: 3, nombre: "Carlos Ruiz" }),
  turno(3, "2026-10-11", "08:00", "16:00", "2026-10-11", null),
];

async function ingresar(page, email = "ana@x.com", password = "secreto1") {
  await page.goto("/");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByRole("button", { name: "Ingresar" }).click();
}

test("el médico ingresa y ve su calendario semanal; todos los pedidos llevan el Bearer", async ({ page }) => {
  await simularSupabase(page);
  const pedidos = await simularApi(page, { me: ME, turnos: TURNOS });
  await ingresar(page);
  await expect(page.getByText("5 al 11 de octubre de 2026")).toBeVisible();
  await expect(page.getByTestId("turno")).toHaveCount(3);
  await expect(page.getByText("Mi guardia")).toBeVisible();
  await expect(page.getByText("20:00 – 08:00 (+1 día)")).toBeVisible();
  await expect(page.getByText("BAJA")).toBeVisible();
  const turnosPedido = pedidos.find((p) => p.ruta === "/api/turnos");
  expect(turnosPedido.consulta).toBe("?desde=2026-10-05&hasta=2026-10-11");
  for (const p of pedidos.filter((p) => p.ruta !== "/api/health")) {
    expect(p.authorization, `${p.metodo} ${p.ruta}`).toMatch(/^Bearer .+\..+\..+$/);
  }
});

test("credenciales incorrectas: mensaje en español y sigue en el login", async ({ page }) => {
  await simularSupabase(page);
  await simularApi(page, { me: ME });
  await ingresar(page, "ana@x.com", "mala");
  await expect(page.getByRole("alert")).toHaveText("Email o contraseña incorrectos.");
  await expect(page.getByRole("button", { name: "Ingresar" })).toBeVisible();
});

test("cuenta PENDIENTE: 'Esperando activación' y Actualizar la pasa al calendario cuando se activa", async ({ page }) => {
  await simularSupabase(page);
  let activa = false;
  await simularApi(page, { me: () => ({ ...ME, estado: activa ? "ACTIVO" : "PENDIENTE" }), turnos: TURNOS });
  await ingresar(page);
  await expect(page.getByRole("heading", { name: "Esperando activación" })).toBeVisible();
  activa = true;
  await page.getByRole("button", { name: "Actualizar" }).click();
  await expect(page.getByText("5 al 11 de octubre de 2026")).toBeVisible();
});

test("registro sin código: crea la cuenta, manda solo el nombre y queda esperando activación", async ({ page }) => {
  await simularSupabase(page);
  const pedidos = await simularApi(page, { me: { ...ME, estado: "PENDIENTE" }, registro: () => ({ status: 201, cuerpo: { ...ME, estado: "PENDIENTE" } }) });
  await page.goto("/");
  await page.getByRole("tab", { name: "Registrarme" }).click();
  await page.getByLabel("Nombre").fill("Ana Gómez");
  await page.getByLabel("Email").fill("ana@x.com");
  await page.getByLabel("Contraseña").fill("secreto1");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page.getByRole("heading", { name: "Esperando activación" })).toBeVisible();
  const registro = pedidos.find((p) => p.ruta === "/api/registro");
  expect(JSON.parse(registro.cuerpo)).toEqual({ nombre: "Ana Gómez" });
  expect(registro.authorization).toMatch(/^Bearer /);
});

test("registro con código de coordinación: queda activo como coordinador", async ({ page }) => {
  await simularSupabase(page);
  const coord = { ...ME, nombre: "Enzo", rol: "COORDINADOR" };
  const pedidos = await simularApi(page, { me: coord, turnos: TURNOS, registro: () => ({ status: 201, cuerpo: coord }) });
  await page.goto("/");
  await page.getByRole("tab", { name: "Registrarme" }).click();
  await page.getByLabel("Nombre").fill("Enzo");
  await page.getByLabel("Email").fill("enzo@x.com");
  await page.getByLabel("Contraseña").fill("secreto1");
  await page.getByLabel("Código de coordinación (opcional)").fill("SMG");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page.getByText(/pantallas de coordinación/i)).toBeVisible();
  expect(JSON.parse(pedidos.find((p) => p.ruta === "/api/registro").cuerpo)).toEqual({ nombre: "Enzo", codigoCoordinacion: "SMG" });
});

test("código incorrecto: ofrece completar el registro y el segundo intento funciona", async ({ page }) => {
  await simularSupabase(page);
  let registrado = false;
  await simularApi(page, {
    me: () => (registrado ? { ...ME, estado: "PENDIENTE" } : { status: 403, cuerpo: { codigo: "USUARIO_NO_REGISTRADO", mensaje: "Falta registro." } }),
    registro: (cuerpo) => {
      if (cuerpo.codigoCoordinacion) return { status: 422, cuerpo: { codigo: "CODIGO_INVALIDO", mensaje: "El código de coordinación no es correcto." } };
      registrado = true;
      return { status: 201, cuerpo: { ...ME, estado: "PENDIENTE" } };
    },
  });
  await page.goto("/");
  await page.getByRole("tab", { name: "Registrarme" }).click();
  await page.getByLabel("Nombre").fill("Ana Gómez");
  await page.getByLabel("Email").fill("ana@x.com");
  await page.getByLabel("Contraseña").fill("secreto1");
  await page.getByLabel("Código de coordinación (opcional)").fill("MAL");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page.getByRole("heading", { name: "Completá tu registro" })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveText("El código de coordinación no es correcto.");
  await page.getByLabel("Nombre").fill("Ana Gómez");
  await page.getByRole("button", { name: "Completar registro" }).click();
  await expect(page.getByRole("heading", { name: "Esperando activación" })).toBeVisible();
});

test("token vencido con la app abierta: vuelve al login con el mensaje", async ({ page }) => {
  await simularSupabase(page);
  let vencido = false;
  await page.route("**/api/turnos**", (ruta) => {
    if (!vencido) return ruta.fallback();
    return ruta.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ codigo: "TOKEN_VENCIDO", mensaje: "La sesión venció. Volvé a ingresar." }) });
  });
  await simularApi(page, { me: ME, turnos: TURNOS });
  await ingresar(page);
  await expect(page.getByText("5 al 11 de octubre de 2026")).toBeVisible();
  vencido = true;
  await page.getByRole("button", { name: "Semana siguiente" }).click();
  await expect(page.getByRole("status")).toContainText("La sesión venció. Volvé a ingresar.");
  await expect(page.getByRole("button", { name: "Ingresar" })).toBeVisible();
});

test("servidor caído al pedir la semana: mensaje y reintento", async ({ page }) => {
  await simularSupabase(page);
  await simularApi(page, { me: ME, turnos: TURNOS });
  await ingresar(page);
  await expect(page.getByText("5 al 11 de octubre de 2026")).toBeVisible();
  await page.route("**/api/turnos**", (ruta) => ruta.abort());
  await page.getByRole("button", { name: "Semana siguiente" }).click();
  await expect(page.getByRole("alert")).toContainText("No se pudo conectar con el servidor");
  await page.unroute("**/api/turnos**");
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page.getByText("12 al 18 de octubre de 2026")).toBeVisible();
});

test("simulado: el médico avisa su ausencia y se postula a una baja", async ({ page }) => {
  await simularSupabase(page);
  await simularApi(page, { me: ME, turnos: TURNOS });
  await ingresar(page);
  await page.locator('[data-turno-id="1:2026-10-09"]').click();
  await expect(page.getByTestId("rotulo-simulado")).toBeVisible();
  await page.getByLabel(/Motivo/).fill("Congreso");
  await page.getByRole("button", { name: "Avisar ausencia" }).click();
  await expect(page.getByRole("button", { name: "Retirar aviso" })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar" }).click();
  await page.locator('[data-turno-id="3:2026-10-11"]').click();
  await page.getByRole("button", { name: "Postularme" }).click();
  await expect(page.getByRole("button", { name: "Retirar postulación" })).toBeVisible();
});

test("en pantalla de celular el calendario no desborda horizontalmente", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 700 });
  await simularSupabase(page);
  await simularApi(page, { me: ME, turnos: TURNOS });
  await ingresar(page);
  await expect(page.getByText("5 al 11 de octubre de 2026")).toBeVisible();
  const desborda = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(desborda).toBe(false);
});
```

- [ ] **Step 3: Contrato contra el backend real `contrato.spec.js`**

```js
import { expect, test } from "@playwright/test";

// Estas pruebas hablan con el backend real (lo levanta playwright.config.js).
test("sin token, la API responde 401 SIN_SESION", async ({ request }) => {
  for (const ruta of ["/api/me", "/api/turnos?desde=2026-10-05&hasta=2026-10-11"]) {
    const respuesta = await request.get(ruta);
    expect(respuesta.status(), ruta).toBe(401);
    expect(await respuesta.json()).toMatchObject({ codigo: "SIN_SESION" });
  }
});

test("GET /api/health es público y trae 'ahora' del reloj del servidor", async ({ request }) => {
  const respuesta = await request.get("/api/health");
  expect(respuesta.status()).toBe(200);
  const cuerpo = await respuesta.json();
  expect(cuerpo.estado).toBe("ok");
  expect(Date.parse(cuerpo.ahora)).not.toBeNaN();
});
```

Si el backend local no tiene `SUPABASE_URL` ni `SUPABASE_JWT_SECRET`, el primer test recibe 503 `AUTH_NO_CONFIGURADA` en lugar de 401: es un problema de entorno, no del frontend; se completa `backend/.env` según `backend/CLAUDE.md`.

- [ ] **Step 4: Borrar el spec viejo y correr todo**

```bash
git rm e2e/health.spec.js
docker compose -f ../docker-compose.yml up -d --wait
npm test && npm run test:e2e
```

Expected: Vitest y Playwright en verde. Si falla un selector (`getByText("BAJA")` puede coincidir con más de un elemento si el detalle estuviera abierto; la tarjeta es la única visible en ese momento), ajustar con `.first()` o `exact: true` sin cambiar lo que se verifica.

- [ ] **Step 5: Commit**

```bash
git add e2e
git commit -m "Frontend: pruebas e2e del login, registro, calendario y contrato 401 SIN_SESION (D06, D30)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Verificación real, documentación y registro del proceso

**Files:**
- Modify: `frontend/CLAUDE.md` (nada fuera de `frontend/`)

- [ ] **Step 1: Verificación contra el backend y Supabase reales**

Con `backend/.env` completo y la base migrada y cargada (`alembic upgrade head`, `python -m scripts.seed --confirmar`), levantar `uvicorn` (puerto 8000) y `npm run dev`. Con Playwright (herramienta de navegador o un script en el scratchpad, no en el repo) verificar: registro de un médico nuevo → "Esperando activación"; ingreso con un médico del seed activo → calendario con sus guardias en la semana de `ahora`; ingreso con el coordinador del seed con el código → aviso de coordinador; navegar semanas. Ver en la pestaña Red que `/api/me` y `/api/turnos` llevan `Authorization: Bearer`. Anotar en el pull request qué se verificó y qué no (por ejemplo, si no se pudo crear una cuenta real de Supabase).

- [ ] **Step 2: Actualizar `frontend/CLAUDE.md`**

Reemplazar el encabezado por una descripción actual y agregar convenciones:

```markdown
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

npm install && npx playwright install chromium   # una vez
npm run dev                                      # http://localhost:5173 (necesita el backend en el puerto 8000)
npm test                                         # Vitest
npm run build                                    # compila en dist/
npm run test:e2e                                 # Playwright; levanta backend y frontend si no están corriendo
```

(En el archivo real, los comandos van dentro de un bloque ```bash como estaba.)

- [ ] **Step 3: Preparar las secciones para la descripción del pull request**

No se editan archivos compartidos. Al abrir el pull request, la descripción lleva dos secciones propias: **"Prompts principales"** (el prompt del pedido de F4 copiado tal cual, el plan aprobado y las correcciones del equipo: no tocar nada fuera de `frontend/`, prompts y desvíos en el PR, Native) y **"Desvíos"** (apartes del agente respecto del plan o del pedido, y todo lo que el contrato del backend no alcanzó, por ejemplo un campo ausente; con el formato de `docs/bitacora-de-desvios.md` para que Florencia lo copie). Los desvíos se acumulan en el libro de ejecución y se avisa en el momento si son de contrato. Si no hubo, la sección dice "Sin desvíos".

- [ ] **Step 4: (sin archivos)** Confirmar que no se tocó nada fuera de `frontend/` y del plan: `git diff main --stat` solo muestra rutas `frontend/` y `docs/superpowers/plans/2026-10-07-f4-frontend-medico.md`.

- [ ] **Step 5: Verificación final antes de dar por terminado**

```bash
cd frontend && npm test && npm run build && npm run test:e2e
git status --short   # sin cambios en backend/
git diff main --name-only | grep -v '^frontend/\|^docs/superpowers/plans/2026-10-07-f4-frontend-medico.md$'   # vacío
```

Expected: todo verde y `backend/` sin cambios.

- [ ] **Step 6: Commit**

```bash
git add frontend/CLAUDE.md
git commit -m "Docs: convenciones del frontend de F4" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Revisión de código de la branch** con superpowers:requesting-code-review antes de abrir el pull request. El pull request lo revisa además otro integrante del equipo en GitHub (CLAUDE.md raíz). La descripción del pull request incluye las secciones "Prompts principales" y "Desvíos" del paso 3.

---

## Auto-revisión

**Cobertura del pedido:**
- Login y registro con campo opcional de código y Supabase Auth: Tareas 4 y 5 (más e2e en la 9).
- Calendario semanal que consume `GET /api/turnos`: Tareas 3 y 7.
- Botones de vacantes y postulaciones con datos simulados: Tarea 8.
- `Authorization: Bearer` en toda llamada; 401 `SIN_SESION` sin él: Tarea 2 (cliente) y Tarea 9 (`contrato.spec.js` y verificación de encabezados en el e2e).
- `GET /api/me` con rol y estado; PENDIENTE muestra "esperando activación": Tareas 4, 5 y 6.
- No tocar `backend/`: restricción global y verificación en la Tarea 10, paso 5.
- Plan en `docs/superpowers/plans`, branch `feature/f4-frontend-medico`, un commit por tarea: este archivo y los commits de cada tarea.
- D05 (React + Vite, responsive): Tarea 7 (grilla responsive, prueba de no-desborde en e2e). La instalabilidad PWA (manifest, service worker) queda para F6, como indica `docs/plan-de-implementacion.md`; no se pidió acá.
- D06 / D30: Tareas 4, 5 y 9. D13: Tareas 3 y 7. D15, D16, D24, D25: Tarea 8 (simulado y rotulado). D27: "hoy" desde el reloj del servidor.

**Placeholders:** ninguno; cada paso de código trae el código. Las notas sobre ajustar selectores en e2e son condicionales a un fallo real, sin cambiar lo verificado.

**Consistencia de nombres:** `crearClienteApi`, `ErrorApi`, `useSesion`, `ContextoSesion`, `SesionProvider`, `estado` (`cargando|anonimo|sin-registro|pendiente|baja|activo|error`), `derivarEstado`, `useVacantesSimuladas`, `DetalleTurno` (`acciones.avisarAusencia/retirarAviso/postularme/retirarPostulacion`), `TarjetaTurno` (`estado.tipo/etiqueta/urgente`) se usan igual en todas las tareas.

**Riesgos conocidos al ejecutar:** (1) `supabase-js` podría validar la forma del JWT de la sesión simulada en el e2e: `tokenFalso` ya tiene forma de JWT; si falla, sembrar `localStorage` con la sesión. (2) La versión exacta de Vitest/jsdom puede pedir ajustar `setup.js`. (3) La prueba "registro sin código no manda codigoCoordinacion" de la Tarea 4 es débil y se reemplaza por la de `completarRegistro` si resulta confusa (indicado en el paso 9).

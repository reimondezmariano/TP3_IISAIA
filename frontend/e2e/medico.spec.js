import { expect, test } from "@playwright/test";
import { simularApi, simularSupabase } from "./ayudas.js";

const ME = { id: 1, nombre: "Ana Gómez", email: "ana@x.com", rol: "MEDICO", estado: "ACTIVO" };
const turno = (horarioId, fecha, hi, hf, finFecha, titular) => ({
  id: `${horarioId}:${fecha}`, horarioId, fecha, inicio: `${fecha}T${hi}:00-03:00`, fin: `${finFecha}T${hf}:00-03:00`, duracionHoras: 8, titular, vacante: null,
});
const TURNOS = [
  turno(1, "2026-10-09", "08:00", "16:00", "2026-10-09", { id: 1, nombre: "Ana Gómez" }),
  { ...turno(2, "2026-10-10", "20:00", "08:00", "2026-10-11", { id: 3, nombre: "Carlos Ruiz" }), vacante: { id: 40, urgente: false, generadaPor: { id: 3, nombre: "Carlos Ruiz" } } },
  turno(3, "2026-10-11", "08:00", "16:00", "2026-10-11", null),
];

async function ingresar(page, email = "ana@x.com", password = "secreto1") {
  await page.goto("/");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).last().click();
}

async function completarRegistro(page, { nombre, email, codigo }) {
  await page.goto("/");
  await page.getByRole("tab", { name: "Registrarme" }).click();
  await page.getByLabel("Nombre").fill(nombre);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Contraseña").fill("secreto1");
  if (codigo) await page.getByLabel("Código de coordinación (opcional)").fill(codigo);
  await page.getByRole("button", { name: "Crear cuenta" }).click();
}

test("el médico ingresa y ve su calendario semanal; todos los pedidos llevan el Bearer", async ({ page }) => {
  await simularSupabase(page);
  const pedidos = await simularApi(page, { me: ME, turnos: TURNOS });
  await ingresar(page);
  await expect(page.getByText("5 al 11 de octubre de 2026")).toBeVisible();
  await expect(page.getByTestId("turno")).toHaveCount(3);
  await expect(page.getByText("Mi guardia")).toBeVisible();
  await expect(page.getByText("20:00 – 08:00 (+1 día)")).toBeVisible();
  await expect(page.getByText("BAJA", { exact: true })).toBeVisible();
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
  await expect(page.getByRole("button", { name: "Ingresar", exact: true }).last()).toBeVisible();
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
  await completarRegistro(page, { nombre: "Ana Gómez", email: "ana@x.com" });
  await expect(page.getByRole("heading", { name: "Esperando activación" })).toBeVisible();
  const registro = pedidos.find((p) => p.ruta === "/api/registro");
  expect(JSON.parse(registro.cuerpo)).toEqual({ nombre: "Ana Gómez" });
  expect(registro.authorization).toMatch(/^Bearer /);
});

test("registro con código de coordinación: queda activo como coordinador", async ({ page }) => {
  await simularSupabase(page);
  const coord = { ...ME, nombre: "Enzo", rol: "COORDINADOR" };
  const pedidos = await simularApi(page, { me: coord, turnos: TURNOS, registro: () => ({ status: 201, cuerpo: coord }) });
  await completarRegistro(page, { nombre: "Enzo", email: "enzo@x.com", codigo: "SMG" });
  await expect(page.getByRole("button", { name: "Staff" })).toBeVisible();
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
  await completarRegistro(page, { nombre: "Ana Gómez", email: "ana@x.com", codigo: "MAL" });
  await expect(page.getByRole("heading", { name: "Completá tu registro" })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveText("El código de coordinación no es correcto.");
  await page.getByLabel("Nombre").fill("Ana Gómez");
  await page.getByRole("button", { name: "Completar registro" }).click();
  await expect(page.getByRole("heading", { name: "Esperando activación" })).toBeVisible();
});

test("token vencido con la app abierta: vuelve al login con el mensaje", async ({ page }) => {
  await simularSupabase(page);
  await simularApi(page, { me: ME, turnos: TURNOS });
  await ingresar(page);
  await expect(page.getByText("5 al 11 de octubre de 2026")).toBeVisible();
  await page.route("**/api/turnos**", (ruta) =>
    ruta.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ codigo: "TOKEN_VENCIDO", mensaje: "La sesión venció. Volvé a ingresar." }) }),
  );
  await page.getByRole("button", { name: "Semana siguiente" }).click();
  await expect(page.getByRole("status")).toContainText("La sesión venció. Volvé a ingresar.");
  await expect(page.getByRole("tab", { name: "Ingresar" })).toBeVisible();
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
  await expect(page.getByText("No hay guardias esta semana.")).toBeVisible();
});

test("el médico se postula con la API real, ve el error si la vacante se cerró y retira la postulación", async ({ page }) => {
  await simularSupabase(page);
  const llamadas = [];
  let miPostulacionId = null; // el servidor informa la postulación activa en GET /turnos
  await simularApi(page, {
    me: ME,
    turnos: () => TURNOS.map((t) => ({ ...t, miPostulacionId: t.id === "3:2026-10-11" ? miPostulacionId : null })),
    extra: (url, peticion, json) => {
      if (peticion.method() !== "POST") return undefined;
      llamadas.push(url.pathname);
      if (url.pathname === "/api/turnos/3:2026-10-11/postulaciones") {
        miPostulacionId = 31;
        return json(201, { id: 31, turnoId: "3:2026-10-11", medico: { id: 1, nombre: "Ana Gómez" }, creadaEn: "2026-10-07T10:00:00-03:00", retiradaEn: null });
      }
      if (url.pathname === "/api/turnos/2:2026-10-10/postulaciones") {
        return json(409, { codigo: "TURNO_SIN_VACANTE", mensaje: "El turno no tiene una vacante abierta." });
      }
      if (url.pathname === "/api/postulaciones/31/retiro") {
        miPostulacionId = null;
        return json(200, { id: 31, turnoId: "3:2026-10-11", medico: { id: 1, nombre: "Ana Gómez" }, creadaEn: "2026-10-07T10:00:00-03:00", retiradaEn: "2026-10-07T10:05:00-03:00" });
      }
      return undefined;
    },
  });
  await ingresar(page);
  await page.locator('[data-turno-id="2:2026-10-10"]').click();
  await page.getByRole("button", { name: "Postularme" }).click();
  await expect(page.getByRole("alert")).toContainText("no tiene una vacante abierta");
  await page.getByRole("button", { name: "Cerrar", exact: true }).click();
  await page.locator('[data-turno-id="3:2026-10-11"]').click();
  await page.getByRole("button", { name: "Postularme" }).click();
  await expect(page.getByRole("button", { name: "Retirar postulación" })).toBeVisible();
  await page.reload();
  await page.locator('[data-turno-id="3:2026-10-11"]').click();
  await page.getByRole("button", { name: "Retirar postulación" }).click();
  await expect(page.getByRole("button", { name: "Postularme" })).toBeVisible();
  expect(llamadas).toEqual(["/api/turnos/2:2026-10-10/postulaciones", "/api/turnos/3:2026-10-11/postulaciones", "/api/postulaciones/31/retiro"]);
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

test("semáforo: cada tarjeta toma su color de la vacante de GET /api/turnos y hay leyenda (D08, D24)", async ({ page }) => {
  await simularSupabase(page);
  const generadaPor = { id: 3, nombre: "Carlos Ruiz" };
  await simularApi(page, {
    me: ME,
    turnos: [
      TURNOS[0],
      { ...TURNOS[1], vacante: { id: 12, urgente: false, generadaPor } },
      { ...turno(4, "2026-10-08", "08:00", "16:00", "2026-10-08", generadaPor), vacante: { id: 13, urgente: true, generadaPor } },
      TURNOS[2],
    ],
  });
  await ingresar(page);
  await expect(page.getByRole("list", { name: "Colores del calendario" })).toBeVisible();
  await expect(page.locator('[data-turno-id="1:2026-10-09"]')).toHaveAttribute("data-semaforo", "cubierta");
  await expect(page.locator('[data-turno-id="2:2026-10-10"]')).toHaveAttribute("data-semaforo", "vacante");
  await expect(page.locator('[data-turno-id="4:2026-10-08"]')).toHaveAttribute("data-semaforo", "urgente");
  await expect(page.locator('[data-turno-id="3:2026-10-11"]')).toHaveAttribute("data-semaforo", "baja");
  await expect(page.locator('[data-turno-id="3:2026-10-11"]')).toHaveCSS("border-left-color", "rgb(178, 58, 36)");
  await page.screenshot({ path: "test-results/semaforo.png", fullPage: true });
});

for (const ancho of [375, 768, 1024, 1280, 1440]) {
  test(`a ${ancho} px el horario de cada tarjeta entra en un renglón y se ve el encabezado`, async ({ page }) => {
    await page.setViewportSize({ width: ancho, height: 900 });
    await simularSupabase(page);
    await simularApi(page, { me: ME, turnos: TURNOS });
    await ingresar(page);
    await expect(page.getByRole("heading", { level: 1, name: "Guardia Viva" })).toBeVisible();
    await expect(page.getByTestId("turno")).toHaveCount(3);
    const renglones = await page.locator(".turno-horario").evaluateAll((spans) =>
      spans.map((s) => ({ texto: s.textContent, ancho: s.scrollWidth, visible: s.clientWidth, alto: s.getBoundingClientRect().height, linea: parseFloat(getComputedStyle(s).lineHeight) })),
    );
    for (const r of renglones) {
      expect(r.ancho, r.texto).toBeLessThanOrEqual(r.visible);
      expect(r.alto, r.texto).toBeLessThan(r.linea * 1.5);
    }
    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(desborde).toBeLessThanOrEqual(0);
    await page.screenshot({ path: `test-results/diseno-${ancho}.png`, fullPage: true });
  });
}

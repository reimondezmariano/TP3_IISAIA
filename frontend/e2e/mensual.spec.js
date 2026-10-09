import { expect, test } from "@playwright/test";
import { simularApi, simularSupabase } from "./ayudas.js";

const MEDICO = { id: 1, nombre: "Ana Gómez", email: "ana@x.com", rol: "MEDICO", estado: "ACTIVO" };
const COORDINADOR = { id: 9, nombre: "Enzo", email: "ana@x.com", rol: "COORDINADOR", estado: "ACTIVO" };
const MARIANO = { id: 3, nombre: "Mariano Reimondez" };
const CARLOS = { id: 4, nombre: "Carlos Lugones" };
const turno = (horarioId, fecha, extra = {}) => ({
  id: `${horarioId}:${fecha}`, horarioId, fecha, inicio: `${fecha}T08:00:00-03:00`, fin: `${fecha}T16:00:00-03:00`, duracionHoras: 8,
  titular: MARIANO, vacante: null, asignado: null, cantidadPostulantes: 0, ...extra,
});

async function ingresar(page) {
  await page.goto("/");
  await page.getByLabel("Email").fill("ana@x.com");
  await page.getByLabel("Contraseña").fill("secreto1");
  await page.getByRole("button", { name: "Ingresar", exact: true }).last().click();
}

test("la tarjeta muestra a quien cubre y el semáforo D34 de una BAJA con postulantes", async ({ page }) => {
  await simularSupabase(page);
  await simularApi(page, {
    me: MEDICO,
    turnos: [
      turno(1, "2026-10-07", { asignado: CARLOS }),
      turno(2, "2026-10-08", { titular: null, asignado: CARLOS }),
      turno(3, "2026-10-09", { titular: null, cantidadPostulantes: 2 }),
    ],
  });
  await ingresar(page);
  await expect(page.getByText("cubre a Mariano Reimondez")).toBeVisible();
  await expect(page.getByText("cubre por baja del titular")).toBeVisible();
  const ambar = page.locator('[data-turno-id="3:2026-10-09"]');
  await expect(ambar).toHaveAttribute("data-semaforo", "baja-postulantes");
  await expect(ambar).toContainText("BAJA");
  await expect(ambar).toContainText("2 postulantes");
});

test("vista mensual en el celular: guardias compactas por día y detalle al tocar", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 700 });
  await simularSupabase(page);
  const pedidos = await simularApi(page, {
    me: MEDICO,
    turnos: (parametros) =>
      parametros.get("desde") === "2026-09-28"
        ? [turno(1, "2026-10-07", { asignado: CARLOS }), turno(2, "2026-10-20", { titular: null, cantidadPostulantes: 1 })]
        : [],
  });
  await ingresar(page);
  await page.getByRole("button", { name: "Mes", exact: true }).click();
  await expect(page.getByRole("heading", { name: "octubre de 2026" })).toBeVisible();
  expect(pedidos.some((p) => p.ruta === "/api/turnos" && p.consulta.includes("desde=2026-09-28") && p.consulta.includes("hasta=2026-11-01"))).toBe(true);
  const chip = page.locator('[data-turno-id="2:2026-10-20"]');
  await expect(chip).toHaveAttribute("data-semaforo", "baja-postulantes");
  // sin desborde horizontal en el celular
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.locator('[data-turno-id="1:2026-10-07"]').click();
  await expect(page.getByRole("dialog")).toContainText("Carlos Lugones, cubre a Mariano Reimondez");
  await page.getByRole("button", { name: "Cerrar", exact: true }).click();
  await page.getByRole("button", { name: "Mes siguiente" }).click();
  await expect(page.getByRole("heading", { name: "noviembre de 2026" })).toBeVisible();
  await page.getByRole("combobox", { name: "Año" }).selectOption("2027");
  await expect(page.getByRole("heading", { name: "noviembre de 2027" })).toBeVisible();
});

test("el coordinador adelanta el reloj de demo y el calendario se recarga; sin modo demo no hay control", async ({ page }) => {
  await simularSupabase(page);
  let ahora = "2026-10-07T10:00:00-03:00";
  const llamadas = [];
  await simularApi(page, {
    me: COORDINADOR,
    turnos: () => [turno(1, "2026-10-07")],
    ahora,
    extra: (url, peticion, json) => {
      if (url.pathname !== "/api/demo/reloj") return undefined;
      const cuerpo = peticion.postDataJSON();
      llamadas.push(cuerpo);
      if (!("ahora" in cuerpo)) return json(422, { codigo: "VALIDACION", mensaje: "body.ahora: Field required" });
      ahora = cuerpo.ahora;
      return json(200, { ahora, desfaseHoras: 24 });
    },
  });
  await ingresar(page);
  await page.getByRole("button", { name: "+1 día" }).click();
  await expect.poll(() => llamadas.filter((c) => "ahora" in c).length).toBe(1);
  expect(llamadas.at(-1).ahora).toBe("2026-10-08T13:00:00.000Z");
  await expect(page.locator('[data-fecha="2026-10-08"]')).toHaveAttribute("aria-current", "date");
});

test("sin modo demo (la ruta responde 404) el coordinador no ve el control del reloj", async ({ page }) => {
  await simularSupabase(page);
  await simularApi(page, {
    me: COORDINADOR,
    turnos: [turno(1, "2026-10-07")],
    extra: (url, peticion, json) => (url.pathname === "/api/demo/reloj" ? json(404, { codigo: "NO_ENCONTRADO", mensaje: "Not Found" }) : undefined),
  });
  await ingresar(page);
  await expect(page.getByTestId("turno")).toBeVisible();
  await expect(page.getByRole("button", { name: "+1 hora" })).toHaveCount(0);
});

test("el coordinador toca NUEVO_REGISTRO en la campanita y llega a Staff", async ({ page }) => {
  await simularSupabase(page);
  await simularApi(page, {
    me: COORDINADOR,
    turnos: [],
    notificaciones: [{ id: 5, tipo: "NUEVO_REGISTRO", mensaje: "Lucía Paz se registró y espera activación", creadaEn: "2026-10-07T09:00:00-03:00", leidaEn: null }],
    extra: (url, peticion, json) => {
      if (url.pathname === "/api/notificaciones/5/leida") return json(200, { id: 5, leidaEn: "2026-10-07T10:00:00-03:00" });
      if (url.pathname === "/api/usuarios" || url.pathname === "/api/horarios") return json(200, []);
      return undefined;
    },
  });
  await ingresar(page);
  await page.getByRole("button", { name: /Notificaciones/ }).click();
  await page.getByRole("button", { name: "Lucía Paz se registró y espera activación" }).click();
  await expect(page.getByRole("heading", { name: "Staff y horarios" })).toBeVisible();
});

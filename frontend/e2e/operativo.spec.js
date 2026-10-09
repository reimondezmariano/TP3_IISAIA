import { expect, test } from "@playwright/test";
import { simularApi, simularSupabase } from "./ayudas.js";

const MEDICO = { id: 1, nombre: "Ana Gómez", email: "ana@x.com", rol: "MEDICO", estado: "ACTIVO" };
const COORDINADOR = { id: 9, nombre: "Enzo", email: "ana@x.com", rol: "COORDINADOR", estado: "ACTIVO" };
const turno = (horarioId, fecha, titular) => ({
  id: `${horarioId}:${fecha}`, horarioId, fecha, inicio: `${fecha}T08:00:00-03:00`, fin: `${fecha}T16:00:00-03:00`, duracionHoras: 8, titular, vacante: null,
});
const ANA = { id: 1, nombre: "Ana Gómez" };

async function ingresar(page) {
  await page.goto("/");
  await page.getByLabel("Email").fill("ana@x.com");
  await page.getByLabel("Contraseña").fill("secreto1");
  await page.getByRole("button", { name: "Ingresar", exact: true }).last().click();
}

test("el médico avisa su ausencia con la API real y la retira usando el id de la vacante que informa el servidor", async ({ page }) => {
  await simularSupabase(page);
  const llamadas = [];
  let vacante = null; // lo que el servidor informa en GET /api/turnos
  await simularApi(page, {
    me: MEDICO,
    turnos: () => [{ ...turno(1, "2026-10-09", ANA), vacante }],
    extra: (url, peticion, json) => {
      if (peticion.method() !== "POST") return undefined;
      llamadas.push({ ruta: url.pathname, cuerpo: peticion.postDataJSON() });
      if (url.pathname === "/api/turnos/1:2026-10-09/vacantes") {
        vacante = { id: 12, urgente: false, generadaPor: ANA };
        return json(201, { id: 12, turnoId: "1:2026-10-09", estado: "ABIERTA", urgente: false, motivo: null, generadaPor: ANA, creadaEn: "2026-10-07T10:00:00-03:00", cerradaEn: null });
      }
      if (url.pathname === "/api/vacantes/12/retiro") {
        vacante = null;
        return json(200, { id: 12, turnoId: "1:2026-10-09", estado: "RETIRADA", urgente: false, generadaPor: ANA, creadaEn: "2026-10-07T10:00:00-03:00", cerradaEn: "2026-10-07T10:01:00-03:00" });
      }
      return undefined;
    },
  });
  await ingresar(page);
  await page.getByTestId("turno").click();
  await page.getByLabel(/Motivo/).fill("Congreso");
  await page.getByRole("button", { name: "Avisar ausencia", exact: true }).click();
  await expect(page.getByRole("button", { name: "Retirar aviso" })).toBeVisible();
  expect(llamadas[0]).toEqual({ ruta: "/api/turnos/1:2026-10-09/vacantes", cuerpo: { motivo: "Congreso" } });
  await page.reload();
  await page.getByTestId("turno").click();
  await page.getByRole("button", { name: "Retirar aviso" }).click();
  await expect(page.getByRole("button", { name: "Avisar ausencia", exact: true })).toBeVisible();
  expect(llamadas.at(-1).ruta).toBe("/api/vacantes/12/retiro");
});

test("el médico avisa varias fechas y ve cuál falló", async ({ page }) => {
  await simularSupabase(page);
  await simularApi(page, {
    me: MEDICO,
    turnos: [turno(1, "2026-10-09", ANA), turno(1, "2026-10-12", ANA)],
    extra: (url, peticion, json) => {
      if (peticion.method() !== "POST") return undefined;
      if (url.pathname.includes("2026-10-12")) return json(409, { codigo: "VACANTE_YA_ABIERTA", mensaje: "El turno ya tiene una vacante abierta." });
      return json(201, { id: 20, turnoId: "1:2026-10-09", estado: "ABIERTA", urgente: false, motivo: null, generadaPor: ANA, creadaEn: "2026-10-07T10:00:00-03:00", cerradaEn: null });
    },
  });
  await ingresar(page);
  await page.getByRole("button", { name: "Avisar ausencia en varias fechas" }).click();
  await page.getByLabel("Hasta").fill("2026-10-13");
  await page.getByRole("button", { name: "Buscar mis guardias" }).click();
  await expect(page.getByRole("checkbox")).toHaveCount(2);
  await page.getByLabel(/Motivo/).fill("Vacaciones");
  await page.getByRole("button", { name: "Avisar 2 fechas" }).click();
  await expect(page.getByText("Se avisó la ausencia en 1 fecha.")).toBeVisible();
  await expect(page.getByText(/ya tiene una vacante abierta/)).toBeVisible();
});

test("el coordinador ve el staff y activa a un médico pendiente", async ({ page }) => {
  await simularSupabase(page);
  let activo = false;
  const pedidos = [];
  await simularApi(page, {
    me: COORDINADOR,
    extra: (url, peticion, json) => {
      if (url.pathname === "/api/usuarios" && peticion.method() === "GET") {
        return json(200, [
          { ...COORDINADOR, fechaBaja: null, horarios: [] },
          { id: 2, nombre: "Beto Díaz", email: "beto@x.com", rol: "MEDICO", estado: activo ? "ACTIVO" : "PENDIENTE", fechaBaja: null, horarios: [] },
        ]);
      }
      if (url.pathname === "/api/horarios") return json(200, []);
      if (url.pathname === "/api/usuarios/2" && peticion.method() === "PATCH") {
        pedidos.push(peticion.postDataJSON());
        activo = true;
        return json(200, { usuario: {}, horariosSinTitular: [], turnosAfectados: [], coberturasReabiertas: [] });
      }
      return undefined;
    },
  });
  await ingresar(page);
  await page.getByRole("button", { name: "Staff" }).click();
  await expect(page.getByText("Pendiente")).toBeVisible();
  await page.getByRole("button", { name: "Activar" }).click();
  await expect(page.getByText("Médico activado.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Activar" })).toHaveCount(0);
  expect(pedidos).toEqual([{ estado: "ACTIVO" }]);
});

test("el médico no ve la pestaña de staff", async ({ page }) => {
  await simularSupabase(page);
  await simularApi(page, { me: MEDICO });
  await ingresar(page);
  await expect(page.getByText("No hay guardias esta semana.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Staff" })).toHaveCount(0);
});

test("campanita con no leídas, aviso emergente de la vacante urgente y marcar como leída", async ({ page }) => {
  await simularSupabase(page);
  let leidas = [];
  const todas = [
    { id: 1, tipo: "VACANTE_URGENTE", mensaje: "Vacante urgente: guardia de mañana 08:00", turnoId: "1:2026-10-08", datos: {}, creadaEn: "2026-10-07T09:00:00-03:00", leidaEn: null },
    { id: 2, tipo: "TURNO_ASIGNADO", mensaje: "Te asignaron la guardia del viernes", turnoId: null, datos: {}, creadaEn: "2026-10-07T08:00:00-03:00", leidaEn: null },
  ];
  await simularApi(page, {
    me: MEDICO,
    notificaciones: () => todas.map((n) => ({ ...n, leidaEn: leidas.includes(n.id) ? "2026-10-07T10:00:00-03:00" : null })),
    extra: (url, peticion, json) => {
      const m = url.pathname.match(/^\/api\/notificaciones\/(\d+)\/leida$/);
      if (m && peticion.method() === "POST") {
        leidas.push(Number(m[1]));
        return json(200, { ...todas[Number(m[1]) - 1], leidaEn: "2026-10-07T10:00:00-03:00" });
      }
      return undefined;
    },
  });
  await ingresar(page);
  await expect(page.getByTestId("contador-notificaciones")).toHaveText("2");
  const aviso = page.getByRole("alert").filter({ hasText: "Vacante urgente: guardia de mañana 08:00" });
  await expect(aviso).toBeVisible();
  await aviso.getByRole("button", { name: "Entendido" }).click();
  await expect(aviso).toHaveCount(0);
  await expect(page.getByTestId("contador-notificaciones")).toHaveText("1");
  await page.getByRole("button", { name: /Notificaciones/ }).click();
  await page.getByRole("button", { name: "Marcar leída" }).click();
  await expect(page.getByTestId("contador-notificaciones")).toHaveCount(0);
});

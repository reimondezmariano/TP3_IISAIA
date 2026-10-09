import { expect, test } from "@playwright/test";
import { simularApi, simularSupabase } from "./ayudas.js";

const COORDINADOR = { id: 9, nombre: "Enzo", email: "ana@x.com", rol: "COORDINADOR", estado: "ACTIVO" };
const CARLOS = { id: 3, nombre: "Carlos Ruiz" };
const TURNO = { id: "2:2026-10-10", horarioId: 2, fecha: "2026-10-10", inicio: "2026-10-10T20:00:00-03:00", fin: "2026-10-11T08:00:00-03:00", duracionHoras: 12, titular: CARLOS, vacante: { id: 41, urgente: false, generadaPor: CARLOS } };
const persona = (id, nombre) => ({ id, nombre });
const candidato = (posicion, id, nombre, extra = {}) => ({ posicion, medico: persona(id, nombre), postuladoEn: "2026-10-08T09:00:00-03:00", coberturasMes: 0, horasSemana: 0, elegible: true, motivoInelegibilidad: null, ...extra });
const USUARIOS = [
  { id: 4, nombre: "Bruno Paz", email: "b@x.com", rol: "MEDICO", estado: "ACTIVO" },
  { id: 5, nombre: "Clara Sosa", email: "c@x.com", rol: "MEDICO", estado: "ACTIVO" },
];

async function ingresar(page) {
  await page.goto("/");
  await page.getByLabel("Email").fill("ana@x.com");
  await page.getByLabel("Contraseña").fill("secreto1");
  await page.getByRole("button", { name: "Ingresar", exact: true }).last().click();
}

test("el coordinador ve los candidatos por equidad, elige uno, reasigna y marca sin cobertura", async ({ page }) => {
  await simularSupabase(page);
  const llamadas = [];
  await simularApi(page, {
    me: COORDINADOR,
    turnos: [TURNO],
    extra: (url, peticion, json) => {
      if (url.pathname === "/api/turnos/2:2026-10-10/candidatos") {
        return json(200, { turnoId: TURNO.id, mes: "2026-10", candidatos: [candidato(1, 4, "Bruno Paz", { horasSemana: 24 }), candidato(2, 5, "Clara Sosa", { coberturasMes: 2, horasSemana: 8 })] });
      }
      if (url.pathname === "/api/usuarios") return json(200, USUARIOS);
      if (url.pathname === "/api/indicadores/sin-cobertura") return json(200, [{ mes: "2026-10", horas: 20, turnos: 2 }]);
      // el sondeo del reloj de demo no es una acción de dominio
      if ((peticion.method() === "PUT" || peticion.method() === "POST") && url.pathname !== "/api/demo/reloj") llamadas.push({ metodo: peticion.method(), ruta: url.pathname, cuerpo: peticion.postDataJSON() });
      if (url.pathname === "/api/turnos/2:2026-10-10/asignacion") {
        const { medicoId, reasignar } = peticion.postDataJSON();
        if (medicoId === 5 && !reasignar) return json(409, { codigo: "YA_TIENE_ASIGNADO", mensaje: "El turno ya tiene asignado: para cambiarlo hay que reasignar." });
        return json(200, { turnoId: TURNO.id, asignado: persona(medicoId, medicoId === 4 ? "Bruno Paz" : "Clara Sosa"), caso: reasignar ? "REASIGNACION" : "CANDIDATO_ELEGIDO", vacante: null });
      }
      if (url.pathname === "/api/turnos/2:2026-10-10/sin-cobertura") {
        return json(200, { turnoId: TURNO.id, sinCoberturaEn: "2026-10-10T21:00:00-03:00", vacanteId: 3 });
      }
      return undefined;
    },
  });
  await ingresar(page);
  await expect(page.getByTestId("indicador-sin-cobertura")).toContainText("20 h sin cobertura en octubre de 2026 (2 turnos)");
  await page.locator('[data-turno-id="2:2026-10-10"]').click();
  const filas = page.getByTestId("candidato");
  await expect(filas).toHaveCount(2);
  await expect(filas.nth(0)).toContainText("Bruno Paz");
  await expect(filas.nth(0)).toContainText("24 h esta semana");
  await filas.nth(0).getByRole("button", { name: "Elegir" }).click();
  await expect(page.getByRole("status")).toContainText("Bruno Paz cubre este turno");
  await filas.nth(1).getByRole("button", { name: "Elegir" }).click();
  await page.getByRole("button", { name: "Reasignar a Clara Sosa" }).click();
  await expect(page.getByRole("status")).toContainText("Clara Sosa cubre este turno");
  await page.getByRole("button", { name: "Marcar sin cobertura" }).click();
  await expect(page.getByRole("status")).toContainText("sin cobertura");
  expect(llamadas.map((l) => [l.metodo, l.ruta, l.cuerpo])).toEqual([
    ["PUT", "/api/turnos/2:2026-10-10/asignacion", { medicoId: 4, reasignar: false }],
    ["PUT", "/api/turnos/2:2026-10-10/asignacion", { medicoId: 5, reasignar: false }],
    ["PUT", "/api/turnos/2:2026-10-10/asignacion", { medicoId: 5, reasignar: true }],
    ["POST", "/api/turnos/2:2026-10-10/sin-cobertura", null],
  ]);
});

test("un médico no ve el panel de cobertura", async ({ page }) => {
  await simularSupabase(page);
  await simularApi(page, { me: { ...COORDINADOR, rol: "MEDICO", id: 1 }, turnos: [TURNO] });
  await ingresar(page);
  await page.locator('[data-turno-id="2:2026-10-10"]').click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("region", { name: "Cobertura del turno" })).toHaveCount(0);
});

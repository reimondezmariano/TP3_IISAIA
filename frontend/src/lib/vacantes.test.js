import { beforeEach, describe, expect, test, vi } from "vitest";
import { generarLote, generarVacante, leerRecordadas, olvidar, recordar, retirarVacante } from "./vacantes.js";

beforeEach(() => window.localStorage.clear());

describe("llamadas a la API", () => {
  test("generarVacante, generarLote y retirarVacante usan las rutas del contrato", async () => {
    const api = { post: vi.fn(async () => ({})) };
    await generarVacante(api, "7:2026-10-17", "Congreso");
    await generarVacante(api, "7:2026-10-24", "");
    await generarLote(api, ["7:2026-10-17", "7:2026-10-24"], "Vacaciones");
    await retirarVacante(api, 12);
    expect(api.post.mock.calls).toEqual([
      ["/api/turnos/7:2026-10-17/vacantes", { motivo: "Congreso" }],
      ["/api/turnos/7:2026-10-24/vacantes", { motivo: null }],
      ["/api/vacantes/lote", { turnoIds: ["7:2026-10-17", "7:2026-10-24"], motivo: "Vacaciones" }],
      ["/api/vacantes/12/retiro"],
    ]);
  });
});

describe("vacantes recordadas", () => {
  test("recordar y olvidar, por usuario", () => {
    recordar(1, "7:2026-10-17", 12);
    recordar(2, "7:2026-10-17", 99);
    expect(leerRecordadas(1)).toEqual({ "7:2026-10-17": 12 });
    olvidar(1, "7:2026-10-17");
    expect(leerRecordadas(1)).toEqual({});
    expect(leerRecordadas(2)).toEqual({ "7:2026-10-17": 99 });
  });

  test("contenido roto o de otro tipo se ignora", () => {
    window.localStorage.setItem("guardia-viva:vacantes:1", "{no es json");
    expect(leerRecordadas(1)).toEqual({});
    window.localStorage.setItem("guardia-viva:vacantes:1", JSON.stringify({ a: "x", b: 4 }));
    expect(leerRecordadas(1)).toEqual({ b: 4 });
    window.localStorage.setItem("guardia-viva:vacantes:1", "[1]");
    expect(leerRecordadas(1)).toEqual({});
  });

  test("si localStorage tira, no se rompe", () => {
    const espia = vi.spyOn(window.localStorage, "setItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    try {
      expect(() => recordar(1, "7:2026-10-17", 12)).not.toThrow();
    } finally {
      espia.mockRestore();
    }
  });
});

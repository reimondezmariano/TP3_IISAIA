import { describe, expect, test, vi } from "vitest";
import { generarLote, generarVacante, retirarVacante } from "./vacantes.js";

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

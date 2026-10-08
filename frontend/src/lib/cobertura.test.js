import { describe, expect, test, vi } from "vitest";
import { asignar, candidatosDe, marcarSinCobertura } from "./cobertura.js";

describe("cobertura: llamadas a la API", () => {
  test("usa las rutas del contrato", async () => {
    const api = { get: vi.fn(async () => ({})), put: vi.fn(async () => ({})), post: vi.fn(async () => ({})) };
    await candidatosDe(api, "7:2026-10-17");
    await asignar(api, "7:2026-10-17", 4, false);
    await asignar(api, "7:2026-10-17", 5, true);
    await marcarSinCobertura(api, "7:2026-10-17");
    expect(api.get).toHaveBeenCalledWith("/api/turnos/7:2026-10-17/candidatos");
    expect(api.put.mock.calls).toEqual([
      ["/api/turnos/7:2026-10-17/asignacion", { medicoId: 4, reasignar: false }],
      ["/api/turnos/7:2026-10-17/asignacion", { medicoId: 5, reasignar: true }],
    ]);
    expect(api.post).toHaveBeenCalledWith("/api/turnos/7:2026-10-17/sin-cobertura");
  });
});

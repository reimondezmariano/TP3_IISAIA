import { describe, expect, test, vi } from "vitest";
import { postular, retirarPostulacion } from "./postulaciones.js";

describe("llamadas a la API", () => {
  test("postular y retirar usan las rutas del contrato", async () => {
    const api = { post: vi.fn(async () => ({})) };
    await postular(api, "7:2026-10-17");
    await retirarPostulacion(api, 31);
    expect(api.post.mock.calls).toEqual([["/api/turnos/7:2026-10-17/postulaciones"], ["/api/postulaciones/31/retiro"]]);
  });
});

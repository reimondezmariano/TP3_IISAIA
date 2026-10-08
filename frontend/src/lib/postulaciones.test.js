import { beforeEach, describe, expect, test, vi } from "vitest";
import { leerRecordadas, olvidar, postular, recordar, retirarPostulacion } from "./postulaciones.js";
import { leerRecordadas as vacantesRecordadas } from "./vacantes.js";

beforeEach(() => window.localStorage.clear());

describe("llamadas a la API", () => {
  test("postular y retirar usan las rutas del contrato", async () => {
    const api = { post: vi.fn(async () => ({})) };
    await postular(api, "7:2026-10-17");
    await retirarPostulacion(api, 31);
    expect(api.post.mock.calls).toEqual([["/api/turnos/7:2026-10-17/postulaciones"], ["/api/postulaciones/31/retiro"]]);
  });
});

describe("postulaciones recordadas", () => {
  test("recordar y olvidar, por usuario y sin mezclarse con las vacantes", () => {
    recordar(1, "7:2026-10-17", 31);
    recordar(2, "7:2026-10-17", 40);
    expect(leerRecordadas(1)).toEqual({ "7:2026-10-17": 31 });
    expect(vacantesRecordadas(1)).toEqual({});
    olvidar(1, "7:2026-10-17");
    expect(leerRecordadas(1)).toEqual({});
    expect(leerRecordadas(2)).toEqual({ "7:2026-10-17": 40 });
  });

  test("contenido roto o almacenamiento bloqueado no rompe", () => {
    window.localStorage.setItem("guardia-viva:postulaciones:1", "{no es json");
    expect(leerRecordadas(1)).toEqual({});
    const espia = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("bloqueado"); });
    expect(() => recordar(1, "7:2026-10-17", 31)).not.toThrow();
    espia.mockRestore();
  });
});

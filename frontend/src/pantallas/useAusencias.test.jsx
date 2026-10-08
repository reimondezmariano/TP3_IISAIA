import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import { leerRecordadas, recordar } from "../lib/vacantes.js";
import { useAusencias } from "./useAusencias.js";

const medico = { id: 1, nombre: "Ana", rol: "MEDICO" };
beforeEach(() => window.localStorage.clear());

describe("useAusencias", () => {
  test("avisar guarda el id de la vacante y lo recuerda", async () => {
    const api = { post: vi.fn(async () => ({ id: 12, turnoId: "7:2026-10-17" })) };
    const { result } = renderHook(() => useAusencias(api, medico));
    await act(() => result.current.avisar("7:2026-10-17", "Congreso"));
    expect(result.current.abiertas).toEqual({ "7:2026-10-17": 12 });
    expect(leerRecordadas(1)).toEqual({ "7:2026-10-17": 12 });
  });

  test("retirar llama al retiro con el id guardado y lo olvida", async () => {
    recordar(1, "7:2026-10-17", 12);
    const api = { post: vi.fn(async () => ({ id: 12 })) };
    const { result } = renderHook(() => useAusencias(api, medico));
    await act(() => result.current.retirar("7:2026-10-17"));
    expect(api.post).toHaveBeenCalledWith("/api/vacantes/12/retiro");
    expect(result.current.abiertas).toEqual({});
    expect(leerRecordadas(1)).toEqual({});
  });

  test("si la vacante ya no está abierta, se olvida y el error se propaga", async () => {
    recordar(1, "7:2026-10-17", 12);
    const api = { post: vi.fn().mockRejectedValue(new ErrorApi(409, "VACANTE_NO_ABIERTA", "La vacante ya no está abierta.")) };
    const { result } = renderHook(() => useAusencias(api, medico));
    await act(async () => {
      await expect(result.current.retirar("7:2026-10-17")).rejects.toThrow("ya no está abierta");
    });
    expect(result.current.abiertas).toEqual({});
  });

  test("otro error al retirar (sin conexión) conserva la vacante", async () => {
    recordar(1, "7:2026-10-17", 12);
    const api = { post: vi.fn().mockRejectedValue(new ErrorApi(0, "SIN_CONEXION", "Sin conexión.")) };
    const { result } = renderHook(() => useAusencias(api, medico));
    await act(async () => {
      await expect(result.current.retirar("7:2026-10-17")).rejects.toThrow();
    });
    expect(result.current.abiertas).toEqual({ "7:2026-10-17": 12 });
  });

  test("varios (médico): de a una; si una falla las demás siguen", async () => {
    let n = 0;
    const api = {
      post: vi.fn(async (ruta) => {
        if (ruta.includes("2026-10-24")) throw new ErrorApi(409, "VACANTE_YA_ABIERTA", "El turno ya tiene una vacante abierta.");
        return { id: ++n };
      }),
    };
    const { result } = renderHook(() => useAusencias(api, medico));
    let resumen;
    await act(async () => {
      resumen = await result.current.avisarVarios(["7:2026-10-17", "7:2026-10-24", "7:2026-10-31"], "Vacaciones");
    });
    expect(resumen.ok).toEqual(["7:2026-10-17", "7:2026-10-31"]);
    expect(resumen.fallaron).toEqual([{ turnoId: "7:2026-10-24", mensaje: "El turno ya tiene una vacante abierta." }]);
    expect(api.post).not.toHaveBeenCalledWith("/api/vacantes/lote", expect.anything());
  });

  test("varios (coordinador): usa el lote", async () => {
    const api = { post: vi.fn(async () => ({ vacantes: [{ turnoId: "7:2026-10-17" }, { turnoId: "7:2026-10-24" }] })) };
    const { result } = renderHook(() => useAusencias(api, { id: 9, rol: "COORDINADOR" }));
    let resumen;
    await act(async () => {
      resumen = await result.current.avisarVarios(["7:2026-10-17", "7:2026-10-24"], "x");
    });
    expect(api.post).toHaveBeenCalledWith("/api/vacantes/lote", { turnoIds: ["7:2026-10-17", "7:2026-10-24"], motivo: "x" });
    expect(resumen.ok).toHaveLength(2);
  });
});

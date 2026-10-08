import { act, renderHook } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import { useAusencias } from "./useAusencias.js";

const medico = { id: 1, nombre: "Ana", rol: "MEDICO" };

describe("useAusencias", () => {
  test("avisar genera la vacante y avisa que hubo un cambio", async () => {
    const api = { post: vi.fn(async () => ({ id: 12, turnoId: "7:2026-10-17" })) };
    const alCambiar = vi.fn();
    const { result } = renderHook(() => useAusencias(api, medico, { alCambiar }));
    await act(() => result.current.avisar("7:2026-10-17", "Congreso"));
    expect(api.post).toHaveBeenCalledWith("/api/turnos/7:2026-10-17/vacantes", { motivo: "Congreso" });
    expect(alCambiar).toHaveBeenCalledTimes(1);
  });

  test("retirar usa el id de la vacante que informa el turno y avisa del cambio", async () => {
    const api = { post: vi.fn(async () => ({ id: 12 })) };
    const alCambiar = vi.fn();
    const { result } = renderHook(() => useAusencias(api, medico, { alCambiar }));
    await act(() => result.current.retirar(12));
    expect(api.post).toHaveBeenCalledWith("/api/vacantes/12/retiro");
    expect(alCambiar).toHaveBeenCalledTimes(1);
  });

  test("si la vacante ya no estaba abierta, el error se propaga y se refresca el calendario", async () => {
    const api = { post: vi.fn().mockRejectedValue(new ErrorApi(409, "VACANTE_NO_ABIERTA", "La vacante ya no está abierta.")) };
    const alCambiar = vi.fn();
    const { result } = renderHook(() => useAusencias(api, medico, { alCambiar }));
    await act(async () => {
      await expect(result.current.retirar(12)).rejects.toThrow("ya no está abierta");
    });
    expect(alCambiar).toHaveBeenCalledTimes(1);
  });

  test("un error de red al retirar no refresca nada", async () => {
    const api = { post: vi.fn().mockRejectedValue(new ErrorApi(0, "SIN_CONEXION", "Sin conexión.")) };
    const alCambiar = vi.fn();
    const { result } = renderHook(() => useAusencias(api, medico, { alCambiar }));
    await act(async () => {
      await expect(result.current.retirar(12)).rejects.toThrow();
    });
    expect(alCambiar).not.toHaveBeenCalled();
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

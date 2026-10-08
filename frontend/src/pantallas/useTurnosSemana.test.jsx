import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import { useTurnosSemana } from "./useTurnosSemana.js";

describe("useTurnosSemana", () => {
  test("pide lunes a domingo y devuelve los turnos", async () => {
    const api = { get: vi.fn().mockResolvedValue([{ id: "1:2026-10-05" }]) };
    const { result } = renderHook(() => useTurnosSemana(api, "2026-10-05", { alCuentaCambiada: vi.fn() }));
    expect(result.current.estado).toBe("cargando");
    await waitFor(() => expect(result.current.estado).toBe("ok"));
    expect(api.get).toHaveBeenCalledWith("/api/turnos", { desde: "2026-10-05", hasta: "2026-10-11" });
    expect(result.current.turnos).toEqual([{ id: "1:2026-10-05" }]);
  });

  test("una respuesta vieja no pisa la semana actual", async () => {
    let resolverVieja;
    const api = {
      get: vi.fn((ruta, { desde }) =>
        desde === "2026-10-05" ? new Promise((r) => { resolverVieja = r; }) : Promise.resolve([{ id: "nueva" }]),
      ),
    };
    const { result, rerender } = renderHook(({ lunes }) => useTurnosSemana(api, lunes, { alCuentaCambiada: vi.fn() }), {
      initialProps: { lunes: "2026-10-05" },
    });
    rerender({ lunes: "2026-10-12" });
    await waitFor(() => expect(result.current.turnos).toEqual([{ id: "nueva" }]));
    await act(async () => resolverVieja([{ id: "vieja" }]));
    expect(result.current.turnos).toEqual([{ id: "nueva" }]);
  });

  test("error: estado error y reintentar vuelve a pedir", async () => {
    const api = { get: vi.fn().mockRejectedValueOnce(new ErrorApi(0, "SIN_CONEXION", "Sin conexión.")).mockResolvedValue([]) };
    const { result } = renderHook(() => useTurnosSemana(api, "2026-10-05", { alCuentaCambiada: vi.fn() }));
    await waitFor(() => expect(result.current.estado).toBe("error"));
    expect(result.current.error.message).toBe("Sin conexión.");
    act(() => result.current.reintentar());
    await waitFor(() => expect(result.current.estado).toBe("ok"));
  });

  test.each(["CUENTA_PENDIENTE", "CUENTA_DADA_DE_BAJA"])("403 %s avisa que la cuenta cambió", async (codigo) => {
    const alCuentaCambiada = vi.fn();
    const api = { get: vi.fn().mockRejectedValue(new ErrorApi(403, codigo, "x")) };
    renderHook(() => useTurnosSemana(api, "2026-10-05", { alCuentaCambiada }));
    await waitFor(() => expect(alCuentaCambiada).toHaveBeenCalledTimes(1));
  });

  test("refrescar vuelve a pedir la semana sin pasar por 'cargando'", async () => {
    const api = { get: vi.fn().mockResolvedValueOnce([{ id: "a", vacante: null }]).mockResolvedValueOnce([{ id: "a", vacante: { id: 12 } }]) };
    const { result } = renderHook(() => useTurnosSemana(api, "2026-10-05", { alCuentaCambiada: vi.fn() }));
    await waitFor(() => expect(result.current.estado).toBe("ok"));
    await act(() => result.current.refrescar());
    expect(result.current.estado).toBe("ok");
    expect(result.current.turnos).toEqual([{ id: "a", vacante: { id: 12 } }]);
  });

  test("si refrescar falla, se conservan los turnos que ya había", async () => {
    const api = { get: vi.fn().mockResolvedValueOnce([{ id: "a" }]).mockRejectedValueOnce(new ErrorApi(0, "SIN_CONEXION", "Sin conexión.")) };
    const { result } = renderHook(() => useTurnosSemana(api, "2026-10-05", { alCuentaCambiada: vi.fn() }));
    await waitFor(() => expect(result.current.estado).toBe("ok"));
    await act(() => result.current.refrescar());
    expect(result.current.estado).toBe("ok");
    expect(result.current.turnos).toEqual([{ id: "a" }]);
  });
});

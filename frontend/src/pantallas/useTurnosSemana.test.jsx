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

  test("refrescar vuelve a pedir sin pasar por 'cargando'", async () => {
    const api = { get: vi.fn().mockResolvedValueOnce([{ id: "antes" }]).mockResolvedValue([{ id: "despues" }]) };
    const { result } = renderHook(() => useTurnosSemana(api, "2026-10-05", { alCuentaCambiada: vi.fn() }));
    await waitFor(() => expect(result.current.turnos).toEqual([{ id: "antes" }]));
    act(() => result.current.refrescar());
    expect(result.current.estado).toBe("ok");
    await waitFor(() => expect(result.current.turnos).toEqual([{ id: "despues" }]));
  });

  test("una respuesta de refrescar de la semana anterior no pisa la semana actual", async () => {
    let resolverRefresco;
    const api = {
      get: vi.fn((ruta, { desde }) => {
        if (desde === "2026-10-12") return Promise.resolve([{ id: "semana-b" }]);
        return api.get.mock.calls.filter(([, c]) => c.desde === "2026-10-05").length === 1
          ? Promise.resolve([{ id: "semana-a" }])
          : new Promise((r) => { resolverRefresco = r; });
      }),
    };
    const { result, rerender } = renderHook(({ lunes }) => useTurnosSemana(api, lunes, { alCuentaCambiada: vi.fn() }), { initialProps: { lunes: "2026-10-05" } });
    await waitFor(() => expect(result.current.turnos).toEqual([{ id: "semana-a" }]));
    let refresco;
    act(() => { refresco = result.current.refrescar(); });
    rerender({ lunes: "2026-10-12" });
    await waitFor(() => expect(result.current.turnos).toEqual([{ id: "semana-b" }]));
    await act(async () => { resolverRefresco([{ id: "semana-a-vieja" }]); await refresco; });
    expect(result.current.turnos).toEqual([{ id: "semana-b" }]);
  });

  test("se actualiza solo cada intervalo y un fallo conserva lo que se ve", async () => {
    vi.useFakeTimers();
    try {
      const api = { get: vi.fn().mockResolvedValueOnce([{ id: "antes" }]).mockResolvedValueOnce([{ id: "despues" }]).mockRejectedValue(new ErrorApi(0, "SIN_CONEXION", "x")) };
      const { result } = renderHook(() => useTurnosSemana(api, "2026-10-05", { alCuentaCambiada: vi.fn(), intervaloMs: 1000 }));
      await act(async () => {});
      expect(result.current.turnos).toEqual([{ id: "antes" }]);
      await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
      expect(result.current.turnos).toEqual([{ id: "despues" }]);
      await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
      expect(result.current.estado).toBe("ok");
      expect(result.current.turnos).toEqual([{ id: "despues" }]);
    } finally {
      vi.useRealTimers();
    }
  });
});

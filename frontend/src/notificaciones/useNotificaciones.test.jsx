import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import { useNotificaciones } from "./useNotificaciones.js";

const n = (id, tipo = "TURNO_ASIGNADO", leidaEn = null) => ({ id, tipo, mensaje: `m${id}`, turnoId: null, datos: {}, creadaEn: "2026-10-08T10:00:00-03:00", leidaEn });

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

const montar = (api) => renderHook(() => useNotificaciones(api, { intervaloMs: 12_000 }));
const pasar = (ms) => act(() => vi.advanceTimersByTimeAsync(ms));

describe("useNotificaciones", () => {
  test("consulta al montar y cada 12 s, y deja de consultar al desmontar", async () => {
    const api = { get: vi.fn(async () => [n(1), n(2, "TURNO_ASIGNADO", "2026-10-08T11:00:00-03:00")]) };
    const { result, unmount } = montar(api);
    await pasar(0);
    expect(api.get).toHaveBeenCalledWith("/api/notificaciones");
    expect(result.current.noLeidas).toBe(1);
    await pasar(12_000);
    await pasar(12_000);
    expect(api.get).toHaveBeenCalledTimes(3);
    unmount();
    await pasar(36_000);
    expect(api.get).toHaveBeenCalledTimes(3);
  });

  test("si la consulta falla conserva la lista anterior y reintenta", async () => {
    const api = { get: vi.fn().mockResolvedValueOnce([n(1)]).mockRejectedValueOnce(new ErrorApi(0, "SIN_CONEXION", "x")).mockResolvedValue([n(1), n(2)]) };
    const { result } = montar(api);
    await pasar(0);
    await pasar(12_000);
    expect(result.current.lista).toHaveLength(1);
    await pasar(12_000);
    expect(result.current.lista).toHaveLength(2);
  });

  test("la vacante urgente sin leer se ofrece una sola vez, aunque siga en la lista", async () => {
    const api = { get: vi.fn(async () => [n(5, "VACANTE_URGENTE")]) };
    const { result } = montar(api);
    await pasar(0);
    expect(result.current.urgentes.map((u) => u.id)).toEqual([5]);
    act(() => result.current.descartarUrgente(5));
    await pasar(12_000);
    expect(result.current.urgentes).toEqual([]);
  });

  test("una urgente ya leída no se ofrece", async () => {
    const api = { get: vi.fn(async () => [n(5, "VACANTE_URGENTE", "2026-10-08T10:30:00-03:00")]) };
    const { result } = montar(api);
    await pasar(0);
    expect(result.current.urgentes).toEqual([]);
  });

  test("marcarLeida llama al servidor y baja el contador", async () => {
    const api = { get: vi.fn(async () => [n(1), n(2)]), post: vi.fn(async () => ({ leidaEn: "2026-10-08T12:00:00-03:00" })) };
    const { result } = montar(api);
    await pasar(0);
    await act(() => result.current.marcarLeida(1));
    expect(api.post).toHaveBeenCalledWith("/api/notificaciones/1/leida");
    expect(result.current.noLeidas).toBe(1);
  });

  test("marcarTodas marca cada no leída", async () => {
    const api = { get: vi.fn(async () => [n(1), n(2), n(3, "X", "2026-10-08T10:30:00-03:00")]), post: vi.fn(async () => ({ leidaEn: "2026-10-08T12:00:00-03:00" })) };
    const { result } = montar(api);
    await pasar(0);
    await act(() => result.current.marcarTodas());
    expect(api.post).toHaveBeenCalledTimes(2);
    expect(result.current.noLeidas).toBe(0);
  });

  test("marcarLeida con error del servidor lo propaga y no cambia la lista", async () => {
    const api = { get: vi.fn(async () => [n(1)]), post: vi.fn().mockRejectedValue(new ErrorApi(404, "NOTIFICACION_NO_ENCONTRADA", "No existe.")) };
    const { result } = montar(api);
    await pasar(0);
    await act(async () => {
      await expect(result.current.marcarLeida(1)).rejects.toThrow("No existe.");
    });
    expect(result.current.noLeidas).toBe(1);
  });
});

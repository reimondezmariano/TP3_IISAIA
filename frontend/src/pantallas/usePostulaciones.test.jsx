import { act, renderHook } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import { usePostulaciones } from "./usePostulaciones.js";

describe("usePostulaciones", () => {
  test("postular llama a la API y recarga el calendario", async () => {
    const api = { post: vi.fn(async () => ({ id: 31, turnoId: "7:2026-10-17" })) };
    const alCambiar = vi.fn();
    const { result } = renderHook(() => usePostulaciones(api, { alCambiar }));
    await act(() => result.current.postular("7:2026-10-17"));
    expect(api.post).toHaveBeenCalledWith("/api/turnos/7:2026-10-17/postulaciones");
    expect(alCambiar).toHaveBeenCalledTimes(1);
  });

  test("si el servidor rechaza la postulación, no recarga y el error se propaga", async () => {
    const api = { post: vi.fn(async () => { throw new ErrorApi(409, "TURNO_SIN_VACANTE", "El turno no tiene una vacante abierta."); }) };
    const alCambiar = vi.fn();
    const { result } = renderHook(() => usePostulaciones(api, { alCambiar }));
    await act(async () => {
      await expect(result.current.postular("7:2026-10-17")).rejects.toThrow("vacante abierta");
    });
    expect(alCambiar).not.toHaveBeenCalled();
  });

  test("retirar llama al retiro con el id de la postulación y recarga", async () => {
    const api = { post: vi.fn(async () => ({ id: 31 })) };
    const alCambiar = vi.fn();
    const { result } = renderHook(() => usePostulaciones(api, { alCambiar }));
    await act(() => result.current.retirar(31));
    expect(api.post).toHaveBeenCalledWith("/api/postulaciones/31/retiro");
    expect(alCambiar).toHaveBeenCalledTimes(1);
  });

  test.each([["POSTULACION_YA_RETIRADA", 409], ["POSTULACION_NO_ENCONTRADA", 404]])("si el servidor dice %s, recarga y propaga el error", async (codigo, status) => {
    const api = { post: vi.fn(async () => { throw new ErrorApi(status, codigo, "ya no"); }) };
    const alCambiar = vi.fn();
    const { result } = renderHook(() => usePostulaciones(api, { alCambiar }));
    await act(async () => {
      await expect(result.current.retirar(31)).rejects.toThrow("ya no");
    });
    expect(alCambiar).toHaveBeenCalledTimes(1);
  });

  test("un error de red al retirar no recarga", async () => {
    const api = { post: vi.fn(async () => { throw new ErrorApi(0, "SIN_CONEXION", "sin red"); }) };
    const alCambiar = vi.fn();
    const { result } = renderHook(() => usePostulaciones(api, { alCambiar }));
    await act(async () => {
      await expect(result.current.retirar(31)).rejects.toThrow("sin red");
    });
    expect(alCambiar).not.toHaveBeenCalled();
  });
});

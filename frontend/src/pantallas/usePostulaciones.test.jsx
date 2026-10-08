import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import { leerRecordadas, recordar } from "../lib/postulaciones.js";
import { usePostulaciones } from "./usePostulaciones.js";

const medico = { id: 1, nombre: "Ana", rol: "MEDICO" };
beforeEach(() => window.localStorage.clear());

describe("usePostulaciones", () => {
  test("postular guarda el id de la postulación y lo recuerda", async () => {
    const api = { post: vi.fn(async () => ({ id: 31, turnoId: "7:2026-10-17" })) };
    const { result } = renderHook(() => usePostulaciones(api, medico));
    await act(() => result.current.postular("7:2026-10-17"));
    expect(result.current.postuladas).toEqual({ "7:2026-10-17": 31 });
    expect(leerRecordadas(1)).toEqual({ "7:2026-10-17": 31 });
  });

  test("si el servidor rechaza la postulación, no se recuerda nada y el error se propaga", async () => {
    const api = { post: vi.fn(async () => { throw new ErrorApi(409, "TURNO_SIN_VACANTE", "El turno no tiene una vacante abierta."); }) };
    const { result } = renderHook(() => usePostulaciones(api, medico));
    await act(async () => {
      await expect(result.current.postular("7:2026-10-17")).rejects.toThrow("vacante abierta");
    });
    expect(result.current.postuladas).toEqual({});
    expect(leerRecordadas(1)).toEqual({});
  });

  test("retirar llama al retiro con el id guardado y lo olvida", async () => {
    recordar(1, "7:2026-10-17", 31);
    const api = { post: vi.fn(async () => ({ id: 31 })) };
    const { result } = renderHook(() => usePostulaciones(api, medico));
    await act(() => result.current.retirar("7:2026-10-17"));
    expect(api.post).toHaveBeenCalledWith("/api/postulaciones/31/retiro");
    expect(result.current.postuladas).toEqual({});
  });

  test.each([["POSTULACION_YA_RETIRADA", 409], ["POSTULACION_NO_ENCONTRADA", 404]])("si el servidor dice %s, se olvida y se propaga el error", async (codigo, status) => {
    recordar(1, "7:2026-10-17", 31);
    const api = { post: vi.fn(async () => { throw new ErrorApi(status, codigo, "ya no"); }) };
    const { result } = renderHook(() => usePostulaciones(api, medico));
    await act(async () => {
      await expect(result.current.retirar("7:2026-10-17")).rejects.toThrow("ya no");
    });
    expect(result.current.postuladas).toEqual({});
    expect(leerRecordadas(1)).toEqual({});
  });

  test("un error de red al retirar conserva el recuerdo para reintentar", async () => {
    recordar(1, "7:2026-10-17", 31);
    const api = { post: vi.fn(async () => { throw new ErrorApi(0, "SIN_CONEXION", "sin red"); }) };
    const { result } = renderHook(() => usePostulaciones(api, medico));
    await act(async () => {
      await expect(result.current.retirar("7:2026-10-17")).rejects.toThrow("sin red");
    });
    expect(result.current.postuladas).toEqual({ "7:2026-10-17": 31 });
  });
});

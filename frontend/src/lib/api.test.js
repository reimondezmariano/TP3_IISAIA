import { describe, expect, test, vi } from "vitest";
import { crearClienteApi, ErrorApi } from "./api.js";

function respuesta(status, cuerpo) {
  return new Response(cuerpo === undefined ? null : JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function cliente(opciones = {}) {
  const fetchImpl = opciones.fetchImpl ?? vi.fn().mockResolvedValue(respuesta(200, { ok: true }));
  const api = crearClienteApi({
    obtenerToken: opciones.obtenerToken ?? (async () => "tok-123"),
    alSesionInvalida: opciones.alSesionInvalida,
    fetchImpl,
  });
  return { api, fetchImpl };
}

describe("crearClienteApi", () => {
  test("manda Authorization: Bearer con el token de Supabase en cada pedido", async () => {
    const { api, fetchImpl } = cliente();
    await api.get("/api/me");
    await api.post("/api/registro", { nombre: "Ana" });
    for (const [, opciones] of fetchImpl.mock.calls) {
      expect(opciones.headers.Authorization).toBe("Bearer tok-123");
    }
  });

  test("serializa la consulta y omite valores vacíos", async () => {
    const { api, fetchImpl } = cliente();
    await api.get("/api/turnos", { desde: "2026-10-05", hasta: "2026-10-11", otro: undefined });
    expect(fetchImpl.mock.calls[0][0]).toBe("/api/turnos?desde=2026-10-05&hasta=2026-10-11");
  });

  test("el POST manda JSON", async () => {
    const { api, fetchImpl } = cliente();
    await api.post("/api/registro", { nombre: "Ana", codigoCoordinacion: "SMG" });
    const [, opciones] = fetchImpl.mock.calls[0];
    expect(opciones.method).toBe("POST");
    expect(opciones.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(opciones.body)).toEqual({ nombre: "Ana", codigoCoordinacion: "SMG" });
  });

  test("sin token no hace el pedido y falla con SIN_SESION", async () => {
    const { api, fetchImpl } = cliente({ obtenerToken: async () => null });
    await expect(api.get("/api/me")).rejects.toMatchObject({ codigo: "SIN_SESION", status: 401 });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test("convierte {codigo, mensaje} del servidor en ErrorApi", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(respuesta(422, { codigo: "CODIGO_INVALIDO", mensaje: "El código no es correcto." }));
    const { api } = cliente({ fetchImpl });
    const error = await api.post("/api/registro", {}).catch((e) => e);
    expect(error).toBeInstanceOf(ErrorApi);
    expect(error).toMatchObject({ status: 422, codigo: "CODIGO_INVALIDO", message: "El código no es correcto." });
  });

  test.each(["SIN_SESION", "TOKEN_VENCIDO", "TOKEN_INVALIDO"])("401 %s avisa que la sesión no sirve", async (codigo) => {
    const fetchImpl = vi.fn().mockResolvedValue(respuesta(401, { codigo, mensaje: "Volvé a ingresar." }));
    const alSesionInvalida = vi.fn();
    const { api } = cliente({ fetchImpl, alSesionInvalida });
    await expect(api.get("/api/turnos")).rejects.toMatchObject({ codigo });
    expect(alSesionInvalida).toHaveBeenCalledTimes(1);
  });

  test("un 403 no cierra la sesión", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(respuesta(403, { codigo: "CUENTA_PENDIENTE", mensaje: "Pendiente." }));
    const alSesionInvalida = vi.fn();
    const { api } = cliente({ fetchImpl, alSesionInvalida });
    await expect(api.get("/api/turnos")).rejects.toMatchObject({ codigo: "CUENTA_PENDIENTE" });
    expect(alSesionInvalida).not.toHaveBeenCalled();
  });

  test("falla de red: SIN_CONEXION con mensaje legible", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const { api } = cliente({ fetchImpl });
    await expect(api.get("/api/me")).rejects.toMatchObject({ codigo: "SIN_CONEXION", status: 0 });
  });

  test("error con cuerpo que no es JSON: código HTTP_<status>", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response("<html>Bad gateway</html>", { status: 502 }));
    const { api } = cliente({ fetchImpl });
    await expect(api.get("/api/me")).rejects.toMatchObject({ codigo: "HTTP_502", status: 502 });
  });

  test("204 devuelve undefined", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    const { api } = cliente({ fetchImpl });
    await expect(api.post("/api/x")).resolves.toBeUndefined();
  });

  test("patch manda PATCH con cuerpo JSON y Bearer", async () => {
    const { api, fetchImpl } = cliente();
    await api.patch("/api/usuarios/3", { rol: "COORDINADOR" });
    const [ruta, opciones] = fetchImpl.mock.calls[0];
    expect(ruta).toBe("/api/usuarios/3");
    expect(opciones.method).toBe("PATCH");
    expect(opciones.headers.Authorization).toBe("Bearer tok-123");
    expect(JSON.parse(opciones.body)).toEqual({ rol: "COORDINADOR" });
  });

  test("put manda PUT con cuerpo JSON y Bearer", async () => {
    const { api, fetchImpl } = cliente();
    await api.put("/api/turnos/7:2026-10-17/asignacion", { medicoId: 4, reasignar: false });
    const [ruta, opciones] = fetchImpl.mock.calls[0];
    expect(ruta).toBe("/api/turnos/7:2026-10-17/asignacion");
    expect(opciones.method).toBe("PUT");
    expect(opciones.headers.Authorization).toBe("Bearer tok-123");
    expect(JSON.parse(opciones.body)).toEqual({ medicoId: 4, reasignar: false });
  });
});

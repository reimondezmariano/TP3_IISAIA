import { describe, expect, test, vi } from "vitest";
import { registrarServiceWorker } from "./pwa.js";

describe("registrarServiceWorker", () => {
  test("en producción registra /sw.js", async () => {
    const register = vi.fn(async () => ({}));
    await registrarServiceWorker({ navegador: { serviceWorker: { register } }, produccion: true });
    expect(register).toHaveBeenCalledWith("/sw.js");
  });

  test("en desarrollo no registra nada", async () => {
    const register = vi.fn();
    await registrarServiceWorker({ navegador: { serviceWorker: { register } }, produccion: false });
    expect(register).not.toHaveBeenCalled();
  });

  test("sin soporte de service worker no falla", async () => {
    await expect(registrarServiceWorker({ navegador: {}, produccion: true })).resolves.toBeUndefined();
  });

  test("si el registro falla, la app sigue", async () => {
    const register = vi.fn(async () => { throw new Error("bloqueado"); });
    await expect(registrarServiceWorker({ navegador: { serviceWorker: { register } }, produccion: true })).resolves.toBeUndefined();
  });
});

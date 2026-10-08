import { expect, test } from "@playwright/test";

// Estas pruebas hablan con el backend real (lo levanta playwright.config.js).
test("sin token, la API responde 401 SIN_SESION", async ({ request }) => {
  for (const ruta of ["/api/me", "/api/turnos?desde=2026-10-05&hasta=2026-10-11"]) {
    const respuesta = await request.get(ruta);
    expect(respuesta.status(), ruta).toBe(401);
    expect(await respuesta.json()).toMatchObject({ codigo: "SIN_SESION" });
  }
});

test("GET /api/health es público y trae 'ahora' del reloj del servidor", async ({ request }) => {
  const respuesta = await request.get("/api/health");
  expect(respuesta.status()).toBe(200);
  const cuerpo = await respuesta.json();
  expect(cuerpo.estado).toBe("ok");
  expect(Date.parse(cuerpo.ahora)).not.toBeNaN();
});

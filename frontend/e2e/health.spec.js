import { expect, test } from "@playwright/test";

test("la página muestra el estado del servidor", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Guardia Viva" })).toBeVisible();
  await expect(page.getByTestId("estado")).toHaveText("ok");
  await expect(page.getByTestId("base")).toHaveText("ok");
  await expect(page.getByTestId("ahora")).not.toBeEmpty();
});

test("si el servidor responde con error, se muestra el mensaje", async ({ page }) => {
  await page.route("**/api/health", (ruta) =>
    ruta.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ codigo: "BASE_NO_DISPONIBLE", mensaje: "No se pudo conectar con la base de datos." }),
    }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("No se pudo conectar con la base de datos.");
});

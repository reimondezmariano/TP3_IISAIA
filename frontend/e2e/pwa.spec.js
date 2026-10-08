import { expect, test } from "@playwright/test";

test("la app se puede instalar: enlaza un manifest con íconos y sirve el service worker", async ({ page, request }) => {
  await page.goto("/");
  const href = await page.locator('link[rel="manifest"]').getAttribute("href");
  const manifest = await (await request.get(href)).json();
  expect(manifest).toMatchObject({ short_name: "Guardia Viva", display: "standalone", start_url: "/" });
  for (const icono of manifest.icons) expect((await request.get(icono.src)).ok()).toBe(true);
  expect(manifest.icons.map((i) => i.sizes)).toEqual(expect.arrayContaining(["192x192", "512x512"]));
  expect((await request.get("/sw.js")).ok()).toBe(true);
});

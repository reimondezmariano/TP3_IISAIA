import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());

// Algunas versiones de Node traen un `localStorage` propio que tapa el de jsdom y no funciona sin
// archivo: se instala uno en memoria para las pruebas.
if (typeof window.localStorage?.getItem !== "function") {
  const datos = new Map();
  const almacen = {
    getItem: (k) => (datos.has(k) ? datos.get(k) : null),
    setItem: (k, v) => void datos.set(k, String(v)),
    removeItem: (k) => void datos.delete(k),
    clear: () => datos.clear(),
  };
  Object.defineProperty(window, "localStorage", { value: almacen, configurable: true });
}

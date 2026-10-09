import { describe, expect, test } from "vitest";
import { quienCubre } from "./quienCubre.js";

const titular = { id: 3, nombre: "Mariano Reimondez" };
const asignado = { id: 4, nombre: "Carlos Lugones" };

describe("quienCubre", () => {
  test("sin asignado: el titular", () => {
    expect(quienCubre({ titular, asignado: null })).toEqual({ principal: "Mariano Reimondez", secundario: null });
    expect(quienCubre({ titular })).toEqual({ principal: "Mariano Reimondez", secundario: null });
  });

  test("con asignado: él es el principal y el titular, el dato secundario", () => {
    expect(quienCubre({ titular, asignado })).toEqual({ principal: "Carlos Lugones", secundario: "cubre a Mariano Reimondez" });
  });

  test("titular en BAJA con asignado: cubre por baja del titular", () => {
    expect(quienCubre({ titular: null, asignado })).toEqual({ principal: "Carlos Lugones", secundario: "cubre por baja del titular" });
  });

  test("sin titular ni asignado: Sin titular", () => {
    expect(quienCubre({ titular: null, asignado: null })).toEqual({ principal: "Sin titular", secundario: null });
  });

  test("asignado igual al titular: se muestra una sola vez", () => {
    expect(quienCubre({ titular, asignado: titular })).toEqual({ principal: "Mariano Reimondez", secundario: null });
  });
});

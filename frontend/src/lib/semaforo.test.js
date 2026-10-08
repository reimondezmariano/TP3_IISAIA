import { describe, expect, test } from "vitest";
import { semaforo } from "./semaforo.js";

const titular = { id: 3, nombre: "Carlos Ruiz" };
const vacante = (urgente) => ({ id: 12, urgente, generadaPor: titular });

describe("semaforo", () => {
  test("con titular y sin vacante: cubierta", () => {
    expect(semaforo({ titular, vacante: null })).toEqual({ clase: "cubierta", etiqueta: null });
    expect(semaforo({ titular })).toEqual({ clase: "cubierta", etiqueta: null });
  });

  test("vacante abierta y vacante urgente", () => {
    expect(semaforo({ titular, vacante: vacante(false) })).toEqual({ clase: "vacante", etiqueta: "Vacante" });
    expect(semaforo({ titular, vacante: vacante(true) })).toEqual({ clase: "urgente", etiqueta: "Vacante urgente" });
  });

  test("sin titular: BAJA aunque tenga vacante (D24)", () => {
    expect(semaforo({ titular: null, vacante: null })).toEqual({ clase: "baja", etiqueta: "BAJA" });
    expect(semaforo({ titular: null, vacante: vacante(true) })).toEqual({ clase: "baja", etiqueta: "BAJA" });
  });

  test("sin cobertura (D19): color propio, distinto de cubierta y de BAJA", () => {
    expect(semaforo({ titular, vacante: null, sinCobertura: true })).toEqual({ clase: "sin-cobertura", etiqueta: "Sin cobertura" });
    expect(semaforo({ titular, vacante: null, sinCobertura: false })).toEqual({ clase: "cubierta", etiqueta: null });
  });
});

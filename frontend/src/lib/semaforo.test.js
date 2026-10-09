import { describe, expect, test } from "vitest";
import { semaforo, textoPostulantes } from "./semaforo.js";

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

  test("BAJA con postulantes (D34): ámbar y conserva la etiqueta BAJA", () => {
    expect(semaforo({ titular: null, vacante: null, cantidadPostulantes: 2 })).toEqual({ clase: "baja-postulantes", etiqueta: "BAJA" });
    expect(semaforo({ titular: null, vacante: vacante(true), cantidadPostulantes: 1 })).toEqual({ clase: "baja-postulantes", etiqueta: "BAJA" });
    expect(semaforo({ titular: null, vacante: null, cantidadPostulantes: 0 })).toEqual({ clase: "baja", etiqueta: "BAJA" });
  });

  test("los postulantes no cambian el color de un turno con titular", () => {
    expect(semaforo({ titular, vacante: null, cantidadPostulantes: 3 })).toEqual({ clase: "cubierta", etiqueta: null });
  });

  test("sin cobertura tiene prioridad sobre BAJA con postulantes", () => {
    expect(semaforo({ titular: null, sinCobertura: true, cantidadPostulantes: 1 }).clase).toBe("sin-cobertura");
  });

  test("textoPostulantes: nada sin postulantes, singular y plural", () => {
    expect(textoPostulantes({})).toBeNull();
    expect(textoPostulantes({ cantidadPostulantes: 0 })).toBeNull();
    expect(textoPostulantes({ cantidadPostulantes: 1 })).toBe("1 postulante");
    expect(textoPostulantes({ cantidadPostulantes: 3 })).toBe("3 postulantes");
  });
});

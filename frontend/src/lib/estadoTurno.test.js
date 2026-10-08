import { describe, expect, test } from "vitest";
import { derivarEstado } from "./estadoTurno.js";

const ahora = "2026-10-07T10:00:00-03:00";
const yo = { id: 1, nombre: "Ana", rol: "MEDICO" };
const otro = { id: 3, nombre: "Carlos" };
const coord = { id: 9, nombre: "Enzo", rol: "COORDINADOR" };

function turnoCon(titular, { fecha = "2026-10-12", inicio = "08:00", fin = "16:00", horarioId = 5 } = {}) {
  return { id: `${horarioId}:${fecha}`, horarioId, fecha, inicio: `${fecha}T${inicio}:00-03:00`, fin: `${fecha}T${fin}:00-03:00`, duracionHoras: 8, titular };
}

describe("derivarEstado", () => {
  test("mi turno futuro: normal, puedo avisar mi ausencia", () => {
    expect(derivarEstado({ turno: turnoCon(yo), usuario: yo, ahora })).toMatchObject({ tipo: "NORMAL", etiqueta: null, acciones: ["AVISAR_AUSENCIA"], urgente: false });
  });

  test("mi turno con aviso abierto: vacante y puedo retirar el aviso", () => {
    expect(derivarEstado({ turno: turnoCon(yo), usuario: yo, ahora, vacanteAbierta: true })).toMatchObject({ tipo: "VACANTE", etiqueta: "Vacante", acciones: ["RETIRAR_AVISO"] });
  });

  test("nunca puedo postularme a mi propio turno (D16)", () => {
    expect(derivarEstado({ turno: turnoCon(yo), usuario: yo, ahora, vacanteAbierta: true }).acciones).not.toContain("POSTULARME");
  });

  test("turno ajeno futuro: puedo postularme; ya postulado, retirar", () => {
    expect(derivarEstado({ turno: turnoCon(otro), usuario: yo, ahora })).toMatchObject({ tipo: "NORMAL", acciones: ["POSTULARME"], postulado: false });
    expect(derivarEstado({ turno: turnoCon(otro), usuario: yo, ahora, postulado: true })).toMatchObject({ acciones: ["RETIRAR_POSTULACION"], postulado: true });
  });

  test("turno ajeno que ya empezó: no se ofrece postularse, pero sí retirar una postulación previa", () => {
    const t = turnoCon(otro, { fecha: "2026-10-07", inicio: "08:00", fin: "16:00" });
    expect(derivarEstado({ turno: t, usuario: yo, ahora }).acciones).toEqual([]);
    expect(derivarEstado({ turno: t, usuario: yo, ahora, postulado: true }).acciones).toEqual(["RETIRAR_POSTULACION"]);
  });

  test("titular null: BAJA, se puede cubrir y no es urgente", () => {
    expect(derivarEstado({ turno: turnoCon(null, { fecha: "2026-10-08" }), usuario: yo, ahora })).toMatchObject({ tipo: "BAJA", etiqueta: "BAJA", urgente: false, acciones: ["POSTULARME"] });
  });

  test("vacante propia con menos de 24 h de anticipación es urgente (D15)", () => {
    const t = turnoCon(yo, { fecha: "2026-10-07", inicio: "20:00", fin: "23:00", horarioId: 1 });
    expect(derivarEstado({ turno: t, usuario: yo, ahora, vacanteAbierta: true })).toMatchObject({ urgente: true, etiqueta: "Vacante urgente" });
  });

  test("vacante con 24 h o más no es urgente; turno ya empezado tampoco", () => {
    const lejos = turnoCon(yo, { fecha: "2026-10-08", inicio: "10:00", fin: "18:00" });
    expect(derivarEstado({ turno: lejos, usuario: yo, ahora, vacanteAbierta: true }).urgente).toBe(false);
    const empezado = turnoCon(yo, { fecha: "2026-10-07", inicio: "08:00", fin: "16:00" });
    expect(derivarEstado({ turno: empezado, usuario: yo, ahora, vacanteAbierta: true }).urgente).toBe(false);
  });

  test("turno ya terminado: PASADO sin acciones", () => {
    expect(derivarEstado({ turno: turnoCon(yo, { fecha: "2026-10-06" }), usuario: yo, ahora })).toMatchObject({ tipo: "PASADO", acciones: [], etiqueta: null });
  });

  test("el coordinador no hace guardias: ninguna acción de médico", () => {
    expect(derivarEstado({ turno: turnoCon(null), usuario: coord, ahora }).acciones).toEqual([]);
    expect(derivarEstado({ turno: turnoCon(otro), usuario: coord, ahora }).acciones).toEqual([]);
  });
});

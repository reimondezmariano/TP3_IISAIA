import { describe, expect, test } from "vitest";
import { derivarEstado, hashTurno } from "./vacantes.js";

const ahora = "2026-10-07T10:00:00-03:00";
const yo = { id: 1, nombre: "Ana", rol: "MEDICO" };
const otro = { id: 3, nombre: "Carlos" };

function turnoCon(titular, { fecha = "2026-10-12", inicio = "08:00", fin = "16:00", horarioId = 5 } = {}) {
  return { id: `${horarioId}:${fecha}`, horarioId, fecha, inicio: `${fecha}T${inicio}:00-03:00`, fin: `${fecha}T${fin}:00-03:00`, duracionHoras: 8, titular };
}
function buscar(condicion) {
  for (let h = 1; h < 500; h++) {
    const t = turnoCon(otro, { horarioId: h });
    if (condicion(hashTurno(t.id))) return t;
  }
  throw new Error("sin turno que cumpla la condición");
}
const turnoAjenoConVacante = () => buscar((h) => h % 5 === 0 && h % 10 !== 0);
const turnoAjenoSinVacante = () => buscar((h) => h % 5 !== 0);
const turnoAjenoConPostulante = () => buscar((h) => h % 10 === 0);

describe("hashTurno", () => {
  test("es determinista y no negativo", () => {
    expect(hashTurno("7:2026-10-10")).toBe(hashTurno("7:2026-10-10"));
    expect(hashTurno("7:2026-10-10")).toBeGreaterThanOrEqual(0);
  });
});

describe("derivarEstado", () => {
  test("mi turno futuro: normal, puedo avisar mi ausencia", () => {
    const e = derivarEstado({ turno: turnoCon(yo), usuario: yo, ahora });
    expect(e).toMatchObject({ tipo: "NORMAL", etiqueta: null, acciones: ["AVISAR_AUSENCIA"], urgente: false });
  });

  test("mi turno con aviso abierto: vacante y puedo retirar el aviso", () => {
    const e = derivarEstado({ turno: turnoCon(yo), usuario: yo, ahora, override: { vacante: true, motivo: "Congreso" } });
    expect(e).toMatchObject({ tipo: "VACANTE", etiqueta: "Vacante", acciones: ["RETIRAR_AVISO"] });
  });

  test("nunca puedo postularme a mi propio turno (D16)", () => {
    const e = derivarEstado({ turno: turnoCon(yo), usuario: yo, ahora, override: { vacante: true } });
    expect(e.acciones).not.toContain("POSTULARME");
  });

  test("turno ajeno con vacante simulada: puedo postularme; ya postulado, retirar", () => {
    const t = turnoAjenoConVacante();
    expect(derivarEstado({ turno: t, usuario: yo, ahora })).toMatchObject({ tipo: "VACANTE", acciones: ["POSTULARME"], postulado: false });
    const e = derivarEstado({ turno: t, usuario: yo, ahora, override: { postulado: true } });
    expect(e).toMatchObject({ acciones: ["RETIRAR_POSTULACION"], postulado: true });
    expect(e.postulantes.map((p) => p.id)).toContain(yo.id);
  });

  test("turno ajeno sin vacante: sin acciones", () => {
    expect(derivarEstado({ turno: turnoAjenoSinVacante(), usuario: yo, ahora })).toMatchObject({ tipo: "NORMAL", acciones: [] });
  });

  test("algunos turnos ajenos traen un postulante simulado", () => {
    const e = derivarEstado({ turno: turnoAjenoConPostulante(), usuario: yo, ahora });
    expect(e.postulantes).toEqual([{ id: -1, nombre: "Florencia" }]);
  });

  test("titular null: BAJA, se puede cubrir y no es urgente", () => {
    const e = derivarEstado({ turno: turnoCon(null, { fecha: "2026-10-08" }), usuario: yo, ahora });
    expect(e).toMatchObject({ tipo: "BAJA", etiqueta: "BAJA", urgente: false, acciones: ["POSTULARME"] });
  });

  test("vacante con menos de 24 h de anticipación es urgente (D15)", () => {
    const t = turnoCon(yo, { fecha: "2026-10-07", inicio: "20:00", fin: "23:00", horarioId: 1 });
    const e = derivarEstado({ turno: t, usuario: yo, ahora, override: { vacante: true } });
    expect(e).toMatchObject({ urgente: true, etiqueta: "Vacante urgente" });
  });

  test("vacante con 24 h o más no es urgente", () => {
    const t = turnoCon(yo, { fecha: "2026-10-08", inicio: "10:00", fin: "18:00" });
    expect(derivarEstado({ turno: t, usuario: yo, ahora, override: { vacante: true } }).urgente).toBe(false);
  });

  test("turno ya terminado: PASADO sin acciones", () => {
    const t = turnoCon(yo, { fecha: "2026-10-06" });
    expect(derivarEstado({ turno: t, usuario: yo, ahora })).toMatchObject({ tipo: "PASADO", acciones: [], etiqueta: null });
  });

  test("turno ya empezado y no terminado: no es urgente", () => {
    const t = turnoCon(yo, { fecha: "2026-10-07", inicio: "08:00", fin: "16:00" });
    const e = derivarEstado({ turno: t, usuario: yo, ahora, override: { vacante: true } });
    expect(e.urgente).toBe(false);
  });

  test("el coordinador no tiene acciones", () => {
    const coord = { id: 9, nombre: "Enzo", rol: "COORDINADOR" };
    expect(derivarEstado({ turno: turnoCon(null), usuario: coord, ahora }).acciones).toEqual([]);
  });
});

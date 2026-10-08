import { describe, expect, test } from "vitest";
import { derivarEstado } from "./estadoTurno.js";

const ahora = "2026-10-07T10:00:00-03:00";
const yo = { id: 1, nombre: "Ana", rol: "MEDICO" };
const otro = { id: 3, nombre: "Carlos" };
const coord = { id: 9, nombre: "Enzo", rol: "COORDINADOR" };
const vacanteDe = (generadaPor, urgente = false) => ({ id: 12, urgente, generadaPor });

function turnoCon(titular, { fecha = "2026-10-12", inicio = "08:00", fin = "16:00", horarioId = 5, vacante = null, asignado = null } = {}) {
  return { id: `${horarioId}:${fecha}`, horarioId, fecha, inicio: `${fecha}T${inicio}:00-03:00`, fin: `${fecha}T${fin}:00-03:00`, duracionHoras: 8, titular, vacante, asignado };
}

describe("derivarEstado: médico", () => {
  test("mi turno futuro sin vacante: normal, puedo avisar mi ausencia", () => {
    expect(derivarEstado({ turno: turnoCon(yo), usuario: yo, ahora })).toMatchObject({ tipo: "NORMAL", etiqueta: null, acciones: ["AVISAR_AUSENCIA"], urgente: false });
  });

  test("mi turno con una vacante que generé yo: puedo retirar el aviso", () => {
    const turno = turnoCon(yo, { vacante: vacanteDe(yo) });
    expect(derivarEstado({ turno, usuario: yo, ahora })).toMatchObject({ tipo: "VACANTE", etiqueta: "Vacante", acciones: ["RETIRAR_AVISO"] });
  });

  test("mi turno con una vacante que generó un coordinador: no puedo retirarla (D15)", () => {
    const turno = turnoCon(yo, { vacante: vacanteDe(coord) });
    expect(derivarEstado({ turno, usuario: yo, ahora })).toMatchObject({ tipo: "VACANTE", acciones: [] });
  });

  test("nunca puedo postularme a mi propio turno (D16)", () => {
    const turno = turnoCon(yo, { vacante: vacanteDe(yo) });
    expect(derivarEstado({ turno, usuario: yo, ahora }).acciones).not.toContain("POSTULARME");
  });

  test("turno ajeno con vacante abierta: puedo postularme; ya postulado, retirar", () => {
    const turno = turnoCon(otro, { vacante: vacanteDe(otro) });
    expect(derivarEstado({ turno, usuario: yo, ahora })).toMatchObject({ tipo: "VACANTE", acciones: ["POSTULARME"], postulado: false });
    expect(derivarEstado({ turno: { ...turno, miPostulacionId: 31 }, usuario: yo, ahora })).toMatchObject({ acciones: ["RETIRAR_POSTULACION"], postulado: true });
  });

  test("turno ajeno sin vacante: no se ofrece postularse", () => {
    expect(derivarEstado({ turno: turnoCon(otro), usuario: yo, ahora })).toMatchObject({ tipo: "NORMAL", acciones: [] });
  });

  test("turno ajeno con vacante que ya empezó: no se ofrece postularse, pero sí retirar una postulación previa", () => {
    const turno = turnoCon(otro, { fecha: "2026-10-07", inicio: "08:00", fin: "16:00", vacante: vacanteDe(otro) });
    expect(derivarEstado({ turno, usuario: yo, ahora }).acciones).toEqual([]);
    expect(derivarEstado({ turno: { ...turno, miPostulacionId: 31 }, usuario: yo, ahora }).acciones).toEqual(["RETIRAR_POSTULACION"]);
  });

  test("titular null: BAJA, se puede cubrir aunque no haya vacante, y no es urgente", () => {
    expect(derivarEstado({ turno: turnoCon(null, { fecha: "2026-10-08" }), usuario: yo, ahora })).toMatchObject({ tipo: "BAJA", etiqueta: "BAJA", urgente: false, acciones: ["POSTULARME"] });
  });

  test("la urgencia la informa el servidor (D15)", () => {
    const turno = turnoCon(yo, { fecha: "2026-10-07", inicio: "20:00", fin: "23:00", vacante: vacanteDe(yo, true) });
    expect(derivarEstado({ turno, usuario: yo, ahora })).toMatchObject({ urgente: true, etiqueta: "Vacante urgente" });
    const noUrgente = turnoCon(yo, { vacante: vacanteDe(yo, false) });
    expect(derivarEstado({ turno: noUrgente, usuario: yo, ahora }).urgente).toBe(false);
  });

  test("turno ya terminado: PASADO sin acciones", () => {
    expect(derivarEstado({ turno: turnoCon(yo, { fecha: "2026-10-06" }), usuario: yo, ahora })).toMatchObject({ tipo: "PASADO", acciones: [], etiqueta: null });
  });
});

describe("derivarEstado: coordinador", () => {
  test("turno con titular y sin vacante: puede generarla", () => {
    expect(derivarEstado({ turno: turnoCon(otro), usuario: coord, ahora }).acciones).toEqual(["GENERAR_VACANTE"]);
  });

  test("turno con vacante abierta: puede retirarla, la haya generado quien la haya generado", () => {
    const turno = turnoCon(otro, { vacante: vacanteDe(otro) });
    expect(derivarEstado({ turno, usuario: coord, ahora })).toMatchObject({ tipo: "VACANTE", acciones: ["RETIRAR_VACANTE"] });
  });

  test("turno BAJA o que ya empezó: no se genera vacante; nunca acciones de médico", () => {
    expect(derivarEstado({ turno: turnoCon(null), usuario: coord, ahora })).toMatchObject({ tipo: "BAJA", acciones: [] });
    const empezado = turnoCon(otro, { fecha: "2026-10-07", inicio: "08:00", fin: "16:00" });
    expect(derivarEstado({ turno: empezado, usuario: coord, ahora }).acciones).toEqual([]);
  });

  test("turno pasado: sin acciones", () => {
    expect(derivarEstado({ turno: turnoCon(otro, { fecha: "2026-10-06" }), usuario: coord, ahora }).acciones).toEqual([]);
  });

  test("el asignado vigente puede avisar ausencia y no puede postularse a su turno (D15, D31)", () => {
    const turno = turnoCon(otro, { asignado: yo });
    expect(derivarEstado({ turno, usuario: yo, ahora }).acciones).toEqual(["AVISAR_AUSENCIA"]);
    const conAviso = turnoCon(otro, { asignado: yo, vacante: vacanteDe(yo) });
    expect(derivarEstado({ turno: conAviso, usuario: yo, ahora }).acciones).toEqual(["RETIRAR_AVISO"]);
  });
});

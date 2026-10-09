import { describe, expect, test } from "vitest";
import {
  agruparPorDia, diasDeSemana, etiquetaDia, etiquetaSemana, fechaLocal, horaLocal, horasHasta,
  etiquetaMes, lunesDe, mesDe, rangoMes, rangoSemana, semanasDeMes, sumarDias, sumarMeses, terminoAntes,
} from "./fechas.js";

describe("semana (empieza el lunes)", () => {
  test.each([
    ["2026-10-05", "2026-10-05"], // lunes
    ["2026-10-07", "2026-10-05"], // miércoles
    ["2026-10-11", "2026-10-05"], // domingo pertenece a la semana que termina
    ["2026-10-12", "2026-10-12"],
  ])("lunesDe(%s) = %s", (fecha, esperado) => {
    expect(lunesDe(fecha)).toBe(esperado);
  });

  test("sumarDias cruza mes y año", () => {
    expect(sumarDias("2026-10-30", 3)).toBe("2026-11-02");
    expect(sumarDias("2026-12-31", 1)).toBe("2027-01-01");
    expect(sumarDias("2026-10-05", -7)).toBe("2026-09-28");
  });

  test("diasDeSemana y rangoSemana", () => {
    expect(diasDeSemana("2026-10-05")).toEqual([
      "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11",
    ]);
    expect(rangoSemana("2026-10-05")).toEqual({ desde: "2026-10-05", hasta: "2026-10-11" });
  });
});

describe("zona horaria de Buenos Aires", () => {
  test("fechaLocal usa la fecha de Buenos Aires, no la de UTC", () => {
    expect(fechaLocal("2026-10-17T02:30:00Z")).toBe("2026-10-16"); // 23:30 del 16 en Buenos Aires
    expect(fechaLocal("2026-10-17T08:00:00-03:00")).toBe("2026-10-17");
  });

  test("horaLocal en 24 h", () => {
    expect(horaLocal("2026-10-17T08:00:00-03:00")).toBe("08:00");
    expect(horaLocal("2026-10-17T20:30:00-03:00")).toBe("20:30");
    expect(horaLocal("2026-10-17T00:00:00-03:00")).toBe("00:00");
  });
});

describe("etiquetas", () => {
  test("etiquetaDia", () => {
    expect(etiquetaDia("2026-10-05")).toBe("lun 5");
    expect(etiquetaDia("2026-10-11")).toBe("dom 11");
  });
  test("etiquetaSemana dentro de un mes y entre meses", () => {
    expect(etiquetaSemana("2026-10-05")).toBe("5 al 11 de octubre de 2026");
    expect(etiquetaSemana("2026-10-26")).toBe("26 de octubre al 1 de noviembre de 2026");
    expect(etiquetaSemana("2026-12-28")).toBe("28 de diciembre de 2026 al 3 de enero de 2027");
  });
});

describe("agruparPorDia", () => {
  const dias = diasDeSemana("2026-10-05");
  const turno = (id, fecha, inicio) => ({ id, fecha, inicio, fin: inicio });

  test("todos los días tienen clave y los turnos van ordenados por inicio", () => {
    const grupos = agruparPorDia(
      [
        turno("b", "2026-10-06", "2026-10-06T20:00:00-03:00"),
        turno("a", "2026-10-06", "2026-10-06T08:00:00-03:00"),
      ],
      dias,
    );
    expect(Object.keys(grupos)).toEqual(dias);
    expect(grupos["2026-10-06"].map((t) => t.id)).toEqual(["a", "b"]);
    expect(grupos["2026-10-05"]).toEqual([]);
  });

  test("un turno que empieza el domingo y termina el lunes figura en el domingo", () => {
    const t = { id: "n", fecha: "2026-10-11", inicio: "2026-10-11T20:00:00-03:00", fin: "2026-10-12T08:00:00-03:00" };
    const grupos = agruparPorDia([t], dias);
    expect(grupos["2026-10-11"]).toEqual([t]);
  });

  test("ignora turnos fuera de la semana", () => {
    const grupos = agruparPorDia([turno("x", "2026-10-20", "2026-10-20T08:00:00-03:00")], dias);
    expect(Object.values(grupos).flat()).toEqual([]);
  });
});

describe("tiempo relativo a ahora", () => {
  const t = { inicio: "2026-10-10T08:00:00-03:00", fin: "2026-10-10T16:00:00-03:00" };
  test("terminoAntes", () => {
    expect(terminoAntes(t, "2026-10-10T16:00:01-03:00")).toBe(true);
    expect(terminoAntes(t, "2026-10-10T12:00:00-03:00")).toBe(false);
  });
  test("horasHasta", () => {
    expect(horasHasta(t, "2026-10-09T20:00:00-03:00")).toBe(12);
    expect(horasHasta(t, "2026-10-10T10:00:00-03:00")).toBe(-2);
  });
});

describe("mes", () => {
  test("mesDe, sumarMeses (cruza de año) y etiquetaMes", () => {
    expect(mesDe("2026-10-17")).toBe("2026-10");
    expect(sumarMeses("2026-10", 1)).toBe("2026-11");
    expect(sumarMeses("2026-12", 1)).toBe("2027-01");
    expect(sumarMeses("2026-01", -1)).toBe("2025-12");
    expect(sumarMeses("2026-03", -14)).toBe("2025-01");
    expect(etiquetaMes("2026-10")).toBe("octubre de 2026");
  });

  test("semanasDeMes: lunes a domingo, completa los bordes con días de los meses vecinos", () => {
    const semanas = semanasDeMes("2026-10"); // el 1/10/2026 es jueves; el 31/10 es sábado
    expect(semanas).toHaveLength(5);
    expect(semanas[0][0]).toBe("2026-09-28");
    expect(semanas[0][3]).toBe("2026-10-01");
    expect(semanas.at(-1)[6]).toBe("2026-11-01");
    expect(semanas.every((s) => s.length === 7)).toBe(true);
  });

  test("un mes que empieza lunes y termina domingo no suma semanas de más (febrero de 2027)", () => {
    const semanas = semanasDeMes("2027-02");
    expect(semanas).toHaveLength(4);
    expect(rangoMes("2027-02")).toEqual({ desde: "2027-02-01", hasta: "2027-02-28" });
  });

  test("rangoMes cubre toda la grilla", () => {
    expect(rangoMes("2026-10")).toEqual({ desde: "2026-09-28", hasta: "2026-11-01" });
  });
});

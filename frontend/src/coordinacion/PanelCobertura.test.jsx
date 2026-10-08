import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import PanelCobertura from "./PanelCobertura.jsx";

const TURNO = "7:2026-10-17";
const persona = (id, nombre) => ({ id, nombre });
const candidato = (posicion, id, nombre, extra = {}) => ({
  posicion, medico: persona(id, nombre), postuladoEn: "2026-10-10T09:00:00-03:00", coberturasMes: 0, horasSemana: 0, elegible: true, motivoInelegibilidad: null, ...extra,
});
const CANDIDATOS = {
  turnoId: TURNO, mes: "2026-10",
  candidatos: [
    candidato(1, 4, "Bruno Paz", { coberturasMes: 0, horasSemana: 24 }),
    candidato(2, 5, "Clara Sosa", { coberturasMes: 2, horasSemana: 8 }),
    candidato(null, 6, "Diego Ruiz", { elegible: false, motivoInelegibilidad: "GUARDIA_SUPERPUESTA", coberturasMes: 1, horasSemana: 16 }),
  ],
};
const USUARIOS = [
  { id: 4, nombre: "Bruno Paz", email: "b@x.com", rol: "MEDICO", estado: "ACTIVO" },
  { id: 5, nombre: "Clara Sosa", email: "c@x.com", rol: "MEDICO", estado: "ACTIVO" },
  { id: 7, nombre: "Eva Luna", email: "e@x.com", rol: "MEDICO", estado: "ACTIVO" },
  { id: 8, nombre: "Fede Gil", email: "f@x.com", rol: "MEDICO", estado: "PENDIENTE" },
  { id: 9, nombre: "Enzo Coord", email: "z@x.com", rol: "COORDINADOR", estado: "ACTIVO" },
];

function montar({ get, put = vi.fn(), post = vi.fn(), alCambiar } = {}) {
  const api = {
    get: get ?? vi.fn(async (ruta) => (ruta.endsWith("/candidatos") ? CANDIDATOS : USUARIOS)),
    put, post,
  };
  render(<PanelCobertura api={api} turnoId={TURNO} alCambiar={alCambiar} />);
  return api;
}

describe("PanelCobertura", () => {
  test("lista los candidatos en el orden del servidor con las horas de la semana como dato", async () => {
    montar();
    const filas = await screen.findAllByTestId("candidato");
    expect(filas.map((f) => within(f).getByTestId("candidato-nombre").textContent)).toEqual(["Bruno Paz", "Clara Sosa", "Diego Ruiz"]);
    expect(filas[0]).toHaveTextContent("24 h esta semana");
    expect(filas[1]).toHaveTextContent("2 coberturas en el mes");
    expect(filas[0]).toHaveTextContent("0 coberturas en el mes");
  });

  test("un candidato no elegible muestra su motivo y no se puede elegir", async () => {
    montar();
    const filas = await screen.findAllByTestId("candidato");
    expect(filas[2]).toHaveTextContent("otra guardia superpuesta");
    expect(within(filas[2]).queryByRole("button")).toBeNull();
    expect(within(filas[0]).getByRole("button", { name: "Elegir" })).toBeVisible();
  });

  test("elegir un candidato lo asigna", async () => {
    const put = vi.fn(async () => ({ turnoId: TURNO, asignado: persona(5, "Clara Sosa"), caso: "CANDIDATO_ELEGIDO", vacante: null }));
    montar({ put });
    const filas = await screen.findAllByTestId("candidato");
    await userEvent.click(within(filas[1]).getByRole("button", { name: "Elegir" }));
    expect(put).toHaveBeenCalledWith(`/api/turnos/${TURNO}/asignacion`, { medicoId: 5, reasignar: false });
    expect(await screen.findByRole("status")).toHaveTextContent("Clara Sosa");
  });

  test("asignación directa: solo médicos activos", async () => {
    const put = vi.fn(async () => ({ turnoId: TURNO, asignado: persona(7, "Eva Luna"), caso: "ASIGNACION_DIRECTA", vacante: null }));
    montar({ put });
    const selector = await screen.findByLabelText("Asignar directamente a");
    expect([...selector.options].map((o) => o.textContent)).toEqual(["Elegí un médico", "Bruno Paz", "Clara Sosa", "Eva Luna"]);
    await userEvent.selectOptions(selector, "7");
    await userEvent.click(screen.getByRole("button", { name: "Asignar" }));
    expect(put).toHaveBeenCalledWith(`/api/turnos/${TURNO}/asignacion`, { medicoId: 7, reasignar: false });
    expect(await screen.findByRole("status")).toHaveTextContent("Eva Luna");
  });

  test("Asignar no hace nada sin elegir un médico", async () => {
    const put = vi.fn();
    montar({ put });
    await screen.findByLabelText("Asignar directamente a");
    await userEvent.click(screen.getByRole("button", { name: "Asignar" }));
    expect(put).not.toHaveBeenCalled();
  });

  test("si el turno ya tiene asignado, ofrece reasignar de forma explícita", async () => {
    const put = vi.fn()
      .mockRejectedValueOnce(new ErrorApi(409, "YA_TIENE_ASIGNADO", "El turno ya tiene asignado: para cambiarlo hay que reasignar."))
      .mockResolvedValueOnce({ turnoId: TURNO, asignado: persona(5, "Clara Sosa"), caso: "REASIGNACION", vacante: null });
    montar({ put });
    const filas = await screen.findAllByTestId("candidato");
    await userEvent.click(within(filas[1]).getByRole("button", { name: "Elegir" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("hay que reasignar");
    expect(put).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Reasignar a Clara Sosa" }));
    expect(put).toHaveBeenLastCalledWith(`/api/turnos/${TURNO}/asignacion`, { medicoId: 5, reasignar: true });
    expect(await screen.findByRole("status")).toHaveTextContent("Clara Sosa");
  });

  test("otro error de asignación se muestra y no ofrece reasignar", async () => {
    const put = vi.fn().mockRejectedValue(new ErrorApi(409, "TURNO_SIN_VACANTE", "El turno no tiene una vacante abierta."));
    montar({ put });
    const filas = await screen.findAllByTestId("candidato");
    await userEvent.click(within(filas[0]).getByRole("button", { name: "Elegir" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("no tiene una vacante abierta");
    expect(screen.queryByRole("button", { name: /Reasignar/ })).toBeNull();
  });

  test("marcar sin cobertura", async () => {
    const post = vi.fn(async () => ({ turnoId: TURNO, sinCoberturaEn: "2026-10-17T09:00:00-03:00", vacanteId: 3 }));
    montar({ post });
    await screen.findAllByTestId("candidato");
    await userEvent.click(screen.getByRole("button", { name: "Marcar sin cobertura" }));
    expect(post).toHaveBeenCalledWith(`/api/turnos/${TURNO}/sin-cobertura`);
    expect(await screen.findByRole("status")).toHaveTextContent("sin cobertura");
  });

  test("si todavía no empezó, el error del servidor al marcar sin cobertura se muestra", async () => {
    const post = vi.fn().mockRejectedValue(new ErrorApi(422, "TURNO_NO_EMPEZO", "Un turno se marca sin cobertura cuando ya empezó (D19)."));
    montar({ post });
    await screen.findAllByTestId("candidato");
    await userEvent.click(screen.getByRole("button", { name: "Marcar sin cobertura" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("ya empezó");
  });

  test("si no se pueden cargar los candidatos, se muestra el error y las acciones siguen disponibles", async () => {
    const get = vi.fn(async (ruta) => {
      if (ruta.endsWith("/candidatos")) throw new ErrorApi(404, "TURNO_NO_ENCONTRADO", "No existe el turno.");
      return USUARIOS;
    });
    montar({ get });
    expect(await screen.findByRole("alert")).toHaveTextContent("No existe el turno");
    expect(screen.getByRole("button", { name: "Marcar sin cobertura" })).toBeVisible();
  });

  test("sin candidatos postulados lo dice", async () => {
    montar({ get: vi.fn(async (ruta) => (ruta.endsWith("/candidatos") ? { turnoId: TURNO, mes: "2026-10", candidatos: [] } : USUARIOS)) });
    expect(await screen.findByText("Nadie se postuló todavía.")).toBeVisible();
  });

  test("después de asignar o de marcar sin cobertura avisa que hay que recargar el calendario", async () => {
    const alCambiar = vi.fn();
    const put = vi.fn(async () => ({ turnoId: TURNO, asignado: persona(4, "Bruno Paz"), caso: "CANDIDATO_ELEGIDO", vacante: null }));
    const post = vi.fn(async () => ({ turnoId: TURNO, sinCoberturaEn: "x", vacanteId: 3 }));
    montar({ put, post, alCambiar });
    const filas = await screen.findAllByTestId("candidato");
    await userEvent.click(within(filas[0]).getByRole("button", { name: "Elegir" }));
    await screen.findByRole("status");
    expect(alCambiar).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Marcar sin cobertura" }));
    await vi.waitFor(() => expect(alCambiar).toHaveBeenCalledTimes(2));
  });

  test("si el servidor rechaza la asignación no se recarga nada", async () => {
    const alCambiar = vi.fn();
    const put = vi.fn().mockRejectedValue(new ErrorApi(409, "TURNO_SIN_VACANTE", "El turno no tiene una vacante abierta."));
    montar({ put, alCambiar });
    const filas = await screen.findAllByTestId("candidato");
    await userEvent.click(within(filas[0]).getByRole("button", { name: "Elegir" }));
    await screen.findByRole("alert");
    expect(alCambiar).not.toHaveBeenCalled();
  });
});

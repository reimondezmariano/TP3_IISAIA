import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import AusenciaVarios from "./AusenciaVarios.jsx";

const AHORA = "2026-10-07T10:00:00-03:00";
const t = (id, fecha, titular, hi = "08:00", vacante = null) => ({ id: `${id}:${fecha}`, horarioId: id, fecha, inicio: `${fecha}T${hi}:00-03:00`, fin: `${fecha}T16:00:00-03:00`, duracionHoras: 8, titular, vacante });
const yo = { id: 1, nombre: "Ana", rol: "MEDICO" };
const TURNOS = [
  t(1, "2026-10-09", { id: 1, nombre: "Ana" }),
  t(1, "2026-10-12", { id: 1, nombre: "Ana" }),
  t(2, "2026-10-10", { id: 3, nombre: "Carlos" }),
  t(1, "2026-10-07", { id: 1, nombre: "Ana" }, "08:00"), // ya empezó
];

function montar({ usuario = yo, avisarVarios = vi.fn(async (ids) => ({ ok: ids, fallaron: [] })), turnos = TURNOS } = {}) {
  const api = { get: vi.fn(async () => turnos) };
  render(<AusenciaVarios api={api} usuario={usuario} ahora={AHORA} ausencias={{ avisarVarios }} onCerrar={vi.fn()} />);
  return { api, avisarVarios };
}

describe("AusenciaVarios", () => {
  test("el médico ve solo sus guardias que no empezaron, con el rango pedido", async () => {
    const { api } = montar();
    await userEvent.click(screen.getByRole("button", { name: "Buscar mis guardias" }));
    expect(api.get).toHaveBeenCalledWith("/api/turnos", { desde: "2026-10-07", hasta: "2026-10-13" });
    expect(await screen.findAllByRole("checkbox")).toHaveLength(2);
  });

  test("manda los turnos elegidos y el motivo; el motivo es obligatorio", async () => {
    const { avisarVarios } = montar();
    await userEvent.click(screen.getByRole("button", { name: "Buscar mis guardias" }));
    await userEvent.click((await screen.findAllByRole("checkbox"))[1]);
    await userEvent.click(screen.getByRole("button", { name: /^Avisar 1 fecha$/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Escribí el motivo");
    await userEvent.type(screen.getByLabelText(/Motivo/), "Vacaciones");
    await userEvent.click(screen.getByRole("button", { name: /^Avisar 1 fecha$/ }));
    expect(avisarVarios).toHaveBeenCalledWith(["1:2026-10-09"], "Vacaciones");
    expect(await screen.findByText("Se avisó la ausencia en 1 fecha.")).toBeVisible();
  });

  test("informa las fechas que fallaron con el mensaje del servidor", async () => {
    const avisarVarios = vi.fn(async () => ({ ok: ["1:2026-10-09"], fallaron: [{ turnoId: "1:2026-10-12", mensaje: "El turno ya tiene una vacante abierta." }] }));
    montar({ avisarVarios });
    await userEvent.click(screen.getByRole("button", { name: "Buscar mis guardias" }));
    await screen.findAllByRole("checkbox");
    await userEvent.type(screen.getByLabelText(/Motivo/), "x");
    await userEvent.click(screen.getByRole("button", { name: /^Avisar 2 fechas$/ }));
    expect(await screen.findByText(/ya tiene una vacante abierta/)).toBeVisible();
  });

  test("rango invertido: error sin llamar al servidor", async () => {
    const { api } = montar();
    await userEvent.clear(screen.getByLabelText("Hasta"));
    await userEvent.type(screen.getByLabelText("Hasta"), "2026-10-01");
    await userEvent.click(screen.getByRole("button", { name: "Buscar mis guardias" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("rango de fechas válido");
    expect(api.get).not.toHaveBeenCalled();
  });

  test("el coordinador ve las guardias de todos con el nombre del titular", async () => {
    montar({ usuario: { id: 9, nombre: "Enzo", rol: "COORDINADOR" } });
    await userEvent.click(screen.getByRole("button", { name: "Buscar guardias" }));
    expect(await screen.findAllByRole("checkbox")).toHaveLength(3);
    expect(screen.getByText(/Carlos/)).toBeVisible();
  });

  test("no ofrece los turnos que ya tienen una vacante abierta", async () => {
    const conVacante = { id: 5, urgente: false, generadaPor: { id: 1, nombre: "Ana" } };
    montar({ turnos: [t(1, "2026-10-09", { id: 1, nombre: "Ana" }, "08:00", conVacante), ...TURNOS.slice(1)] });
    await userEvent.click(screen.getByRole("button", { name: "Buscar mis guardias" }));
    expect(await screen.findAllByRole("checkbox")).toHaveLength(1);
  });
});

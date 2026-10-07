import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import { ContextoSesion } from "../sesion/useSesion.js";
import Calendario from "./Calendario.jsx";

const turno = (horarioId, fecha, hi, hf, titular, finFecha = fecha) => ({
  id: `${horarioId}:${fecha}`, horarioId, fecha,
  inicio: `${fecha}T${hi}:00-03:00`, fin: `${finFecha}T${hf}:00-03:00`, duracionHoras: 8, titular,
});
const SEMANA_ACTUAL = [
  turno(1, "2026-10-05", "08:00", "16:00", { id: 1, nombre: "Ana" }),
  turno(2, "2026-10-07", "20:00", "08:00", { id: 3, nombre: "Carlos" }, "2026-10-08"),
  turno(3, "2026-10-11", "20:00", "08:00", null, "2026-10-12"),
];

function montar({ turnosPorDesde = {}, health = { ahora: "2026-10-07T10:00:00-03:00" }, usuario = { id: 1, nombre: "Ana", rol: "MEDICO", estado: "ACTIVO" } } = {}) {
  const api = {
    get: vi.fn(async (ruta, consulta) => {
      if (ruta === "/api/health") {
        if (health instanceof Error) throw health;
        return health;
      }
      return turnosPorDesde[consulta.desde] ?? [];
    }),
  };
  render(
    <ContextoSesion.Provider value={{ api, usuario, estado: "activo", recargar: vi.fn(), cerrarSesion: vi.fn() }}>
      <Calendario />
    </ContextoSesion.Provider>,
  );
  return api;
}

describe("Calendario", () => {
  test("arranca en la semana de 'ahora' del servidor (lunes a domingo) y muestra los turnos en su día", async () => {
    const api = montar({ turnosPorDesde: { "2026-10-05": SEMANA_ACTUAL } });
    expect(await screen.findByText("5 al 11 de octubre de 2026")).toBeVisible();
    expect(await screen.findAllByTestId("turno")).toHaveLength(3);
    expect(api.get).toHaveBeenCalledWith("/api/turnos", { desde: "2026-10-05", hasta: "2026-10-11" });
    expect(document.querySelectorAll("[data-fecha]")).toHaveLength(7);
    expect(within(document.querySelector('[data-fecha="2026-10-05"]')).getAllByTestId("turno")).toHaveLength(1);
    expect(within(document.querySelector('[data-fecha="2026-10-07"]')).getByText("20:00 – 08:00 (+1 día)")).toBeVisible();
    expect(within(document.querySelector('[data-fecha="2026-10-11"]')).getByText("BAJA")).toBeVisible();
  });

  test("resalta el día de hoy según el servidor", async () => {
    montar({ turnosPorDesde: { "2026-10-05": SEMANA_ACTUAL } });
    await screen.findAllByTestId("turno");
    expect(document.querySelector('[data-fecha="2026-10-07"]')).toHaveAttribute("aria-current", "date");
  });

  test("si /health falla, usa la hora del navegador y sigue andando", async () => {
    montar({ health: new Error("caído") });
    expect(await screen.findByRole("heading", { level: 2 })).toBeVisible();
  });

  test("navega a la semana siguiente, a la anterior y vuelve a hoy", async () => {
    const api = montar({ turnosPorDesde: { "2026-10-12": [turno(9, "2026-10-12", "08:00", "14:00", { id: 3, nombre: "Carlos" })] } });
    await screen.findByText("5 al 11 de octubre de 2026");
    await userEvent.click(screen.getByRole("button", { name: "Semana siguiente" }));
    expect(await screen.findByText("12 al 18 de octubre de 2026")).toBeVisible();
    expect(api.get).toHaveBeenCalledWith("/api/turnos", { desde: "2026-10-12", hasta: "2026-10-18" });
    expect(await screen.findByText("Carlos")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Hoy" }));
    expect(await screen.findByText("5 al 11 de octubre de 2026")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Semana anterior" }));
    expect(await screen.findByText("28 de septiembre al 4 de octubre de 2026")).toBeVisible();
  });

  test("semana sin turnos: estado vacío", async () => {
    montar();
    expect(await screen.findByText("No hay guardias esta semana.")).toBeVisible();
  });

  test("error del servidor: mensaje y Reintentar", async () => {
    const api = montar();
    await screen.findByText("No hay guardias esta semana.");
    api.get.mockRejectedValueOnce(new ErrorApi(0, "SIN_CONEXION", "No se pudo conectar con el servidor."));
    await userEvent.click(screen.getByRole("button", { name: "Semana siguiente" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo conectar con el servidor.");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("No hay guardias esta semana.")).toBeVisible();
  });

  test("el coordinador ve el aviso de que sus pantallas llegan más adelante", async () => {
    montar({ usuario: { id: 9, nombre: "Enzo", rol: "COORDINADOR", estado: "ACTIVO" }, turnosPorDesde: { "2026-10-05": SEMANA_ACTUAL } });
    expect(await screen.findByText(/pantallas de coordinación/i)).toBeVisible();
  });

  test("cerrar sesión", async () => {
    const cerrarSesion = vi.fn();
    render(
      <ContextoSesion.Provider value={{ api: { get: vi.fn().mockResolvedValue([]) }, usuario: { id: 1, nombre: "Ana", rol: "MEDICO" }, estado: "activo", recargar: vi.fn(), cerrarSesion }}>
        <Calendario />
      </ContextoSesion.Provider>,
    );
    await userEvent.click(await screen.findByRole("button", { name: "Cerrar sesión" }));
    expect(cerrarSesion).toHaveBeenCalled();
  });
});

import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import IndicadorSinCobertura from "./IndicadorSinCobertura.jsx";

const AHORA = "2026-10-08T23:30:00-03:00";

describe("IndicadorSinCobertura", () => {
  test("pide el mes de hoy y muestra las horas y los turnos sin cobertura", async () => {
    const api = { get: vi.fn(async () => [{ mes: "2026-10", horas: 20, turnos: 2 }]) };
    render(<IndicadorSinCobertura api={api} ahora={AHORA} />);
    expect(await screen.findByTestId("indicador-sin-cobertura")).toHaveTextContent("20 h sin cobertura en octubre de 2026 (2 turnos)");
    expect(api.get).toHaveBeenCalledWith("/api/indicadores/sin-cobertura", { desde: "2026-10", hasta: "2026-10" });
  });

  test("usa el mes en Buenos Aires aunque en UTC ya sea el siguiente", async () => {
    const api = { get: vi.fn(async () => [{ mes: "2026-10", horas: 0, turnos: 0 }]) };
    render(<IndicadorSinCobertura api={api} ahora="2026-10-31T22:00:00-03:00" />);
    await screen.findByTestId("indicador-sin-cobertura");
    expect(api.get).toHaveBeenCalledWith("/api/indicadores/sin-cobertura", { desde: "2026-10", hasta: "2026-10" });
  });

  test("sin horas sin cobertura lo dice y un turno va en singular", async () => {
    const api = { get: vi.fn().mockResolvedValueOnce([{ mes: "2026-10", horas: 0, turnos: 0 }]).mockResolvedValueOnce([{ mes: "2026-10", horas: 8, turnos: 1 }]) };
    const { unmount } = render(<IndicadorSinCobertura api={api} ahora={AHORA} />);
    expect(await screen.findByTestId("indicador-sin-cobertura")).toHaveTextContent("0 h sin cobertura en octubre de 2026 (0 turnos)");
    unmount();
    render(<IndicadorSinCobertura api={api} ahora={AHORA} />);
    expect(await screen.findByTestId("indicador-sin-cobertura")).toHaveTextContent("(1 turno)");
  });

  test("si el servidor falla, no rompe: muestra un aviso discreto", async () => {
    const api = { get: vi.fn(async () => { throw new ErrorApi(500, "ERROR_INTERNO", "Falló."); }) };
    render(<IndicadorSinCobertura api={api} ahora={AHORA} />);
    expect(await screen.findByText("No se pudo cargar el indicador de horas sin cobertura.")).toBeVisible();
  });
});

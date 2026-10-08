import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { ContextoSesion } from "../sesion/useSesion.js";
import Principal from "./Principal.jsx";

vi.mock("./Calendario.jsx", () => ({ default: () => <p>CALENDARIO</p> }));

describe("Principal", () => {
  test("muestra la campanita con las no leídas y el aviso emergente de la vacante urgente", async () => {
    const api = {
      get: vi.fn(async () => [
        { id: 1, tipo: "VACANTE_URGENTE", mensaje: "Vacante urgente: guardia de mañana 08:00", creadaEn: "2026-10-08T10:00:00-03:00", leidaEn: null },
        { id: 2, tipo: "TURNO_ASIGNADO", mensaje: "Te asignaron un turno", creadaEn: "2026-10-08T09:00:00-03:00", leidaEn: null },
      ]),
    };
    render(
      <ContextoSesion.Provider value={{ api, usuario: { id: 1, rol: "MEDICO" } }}>
        <Principal />
      </ContextoSesion.Provider>,
    );
    expect(await screen.findByTestId("contador-notificaciones")).toHaveTextContent("2");
    expect(await screen.findByRole("alert")).toHaveTextContent("Vacante urgente: guardia de mañana 08:00");
    expect(screen.getByText("CALENDARIO")).toBeVisible();
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

describe("Principal: pantalla de staff", () => {
  const api = { get: vi.fn(async (ruta) => (ruta === "/api/notificaciones" ? [] : ruta === "/api/health" ? { ahora: "2026-10-08T10:00:00-03:00" } : [])) };
  const montar = (rol) =>
    render(
      <ContextoSesion.Provider value={{ api, usuario: { id: 1, nombre: "X", rol } }}>
        <Principal />
      </ContextoSesion.Provider>,
    );

  test("el médico no ve la pestaña Staff", () => {
    montar("MEDICO");
    expect(screen.queryByRole("button", { name: "Staff" })).toBeNull();
  });

  test("el coordinador cambia entre Calendario y Staff", async () => {
    montar("COORDINADOR");
    await userEvent.click(screen.getByRole("button", { name: "Staff" }));
    expect(await screen.findByRole("heading", { name: "Staff y horarios" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Calendario" }));
    expect(screen.getByText("CALENDARIO")).toBeVisible();
  });

  test("tocar NUEVO_REGISTRO lleva al coordinador a la pantalla de staff", async () => {
    const nueva = { id: 9, tipo: "NUEVO_REGISTRO", mensaje: "Ana Gómez espera activación", creadaEn: "2026-10-08T10:00:00-03:00", leidaEn: null };
    const apiConAviso = {
      get: vi.fn(async (ruta) => (ruta === "/api/notificaciones" ? [nueva] : [])),
      post: vi.fn(async () => ({ leidaEn: "2026-10-08T10:05:00-03:00" })),
    };
    render(
      <ContextoSesion.Provider value={{ api: apiConAviso, usuario: { id: 1, nombre: "X", rol: "COORDINADOR" } }}>
        <Principal />
      </ContextoSesion.Provider>,
    );
    await userEvent.click(await screen.findByRole("button", { name: /Notificaciones/ }));
    await userEvent.click(screen.getByRole("button", { name: "Ana Gómez espera activación" }));
    expect(await screen.findByRole("heading", { name: "Staff y horarios" })).toBeVisible();
  });
});

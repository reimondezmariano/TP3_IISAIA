import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import App from "./App.jsx";
import { ContextoSesion } from "./sesion/useSesion.js";

vi.mock("./pantallas/Calendario.jsx", () => ({ default: () => <p>CALENDARIO</p> }));

const montar = (valor) =>
  render(
    <ContextoSesion.Provider value={{ usuario: null, aviso: null, recargar: vi.fn(), cerrarSesion: vi.fn(), ...valor }}>
      <App />
    </ContextoSesion.Provider>,
  );

describe("App", () => {
  test.each([
    ["cargando", /Cargando/],
    ["anonimo", /Guardia Viva/],
    ["sin-registro", /Completá tu registro/],
    ["pendiente", /Esperando activación/],
    ["baja", /Cuenta dada de baja/],
    ["activo", /CALENDARIO/],
  ])("estado %s", (estado, texto) => {
    montar({ estado, aviso: null, iniciarSesion: vi.fn(), registrarse: vi.fn(), completarRegistro: vi.fn() });
    expect(screen.getByText(texto, { selector: "h1, p" })).toBeInTheDocument();
  });

  test("error: muestra el aviso y permite reintentar", async () => {
    const recargar = vi.fn();
    montar({ estado: "error", aviso: "No se pudo conectar con el servidor.", recargar });
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo conectar con el servidor.");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(recargar).toHaveBeenCalled();
  });
});

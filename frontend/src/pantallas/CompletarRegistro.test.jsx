import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { ContextoSesion } from "../sesion/useSesion.js";
import CompletarRegistro from "./CompletarRegistro.jsx";

function montar(nombreSugerido) {
  const completarRegistro = vi.fn(async () => {});
  render(
    <ContextoSesion.Provider value={{ completarRegistro, cerrarSesion: vi.fn(), aviso: null, nombreSugerido }}>
      <CompletarRegistro />
    </ContextoSesion.Provider>,
  );
  return completarRegistro;
}

describe("CompletarRegistro", () => {
  test("el nombre cargado al crear la cuenta llena el campo y se puede editar", async () => {
    const completar = montar("Ana Gómez");
    const campo = screen.getByLabelText("Nombre");
    expect(campo).toHaveValue("Ana Gómez");
    await userEvent.type(campo, " Pérez");
    await userEvent.click(screen.getByRole("button", { name: "Completar registro" }));
    expect(completar).toHaveBeenCalledWith({ nombre: "Ana Gómez Pérez", codigo: "" });
  });

  test("sin nombre sugerido el campo queda vacío", () => {
    montar(undefined);
    expect(screen.getByLabelText("Nombre")).toHaveValue("");
  });
});

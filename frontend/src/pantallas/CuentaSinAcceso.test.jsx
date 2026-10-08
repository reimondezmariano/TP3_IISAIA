import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { ContextoSesion } from "../sesion/useSesion.js";
import CompletarRegistro from "./CompletarRegistro.jsx";
import CuentaSinAcceso from "./CuentaSinAcceso.jsx";

const base = { aviso: null, recargar: vi.fn(), cerrarSesion: vi.fn(), completarRegistro: vi.fn().mockResolvedValue(undefined) };
const montar = (pantalla, valor) =>
  render(<ContextoSesion.Provider value={{ ...base, ...valor }}>{pantalla}</ContextoSesion.Provider>);

describe("CuentaSinAcceso", () => {
  test("PENDIENTE: muestra 'Esperando activación' y permite actualizar y salir", async () => {
    const recargar = vi.fn();
    const cerrarSesion = vi.fn();
    montar(<CuentaSinAcceso />, { estado: "pendiente", usuario: { nombre: "Ana", email: "ana@x.com" }, recargar, cerrarSesion });
    expect(screen.getByRole("heading", { name: "Esperando activación" })).toBeVisible();
    expect(screen.getByText(/Un coordinador tiene que activar tu cuenta/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Actualizar" }));
    await userEvent.click(screen.getByRole("button", { name: "Cerrar sesión" }));
    expect(recargar).toHaveBeenCalled();
    expect(cerrarSesion).toHaveBeenCalled();
  });

  test("BAJA: avisa que la cuenta está dada de baja", () => {
    montar(<CuentaSinAcceso />, { estado: "baja", usuario: { nombre: "Ana", email: "ana@x.com" } });
    expect(screen.getByRole("heading", { name: "Cuenta dada de baja" })).toBeVisible();
  });
});

describe("CompletarRegistro", () => {
  test("muestra el aviso del registro fallido y manda nombre y código", async () => {
    const completarRegistro = vi.fn().mockResolvedValue(undefined);
    montar(<CompletarRegistro />, { estado: "sin-registro", aviso: "El código de coordinación no es correcto.", completarRegistro });
    expect(screen.getByRole("alert")).toHaveTextContent("El código de coordinación no es correcto.");
    await userEvent.type(screen.getByLabelText("Nombre"), "Ana");
    await userEvent.click(screen.getByRole("button", { name: "Completar registro" }));
    expect(completarRegistro).toHaveBeenCalledWith({ nombre: "Ana", codigo: "" });
  });

  test("muestra el error si el segundo intento también falla", async () => {
    montar(<CompletarRegistro />, { estado: "sin-registro", completarRegistro: vi.fn().mockRejectedValue(new Error("El código de coordinación no es correcto.")) });
    await userEvent.type(screen.getByLabelText("Nombre"), "Ana");
    await userEvent.type(screen.getByLabelText(/Código de coordinación \(opcional\)/), "MAL");
    await userEvent.click(screen.getByRole("button", { name: "Completar registro" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El código de coordinación no es correcto.");
  });
});

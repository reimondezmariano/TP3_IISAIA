import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { ContextoSesion } from "../sesion/useSesion.js";
import Acceso from "./Acceso.jsx";

function montar(valor = {}) {
  const contexto = {
    estado: "anonimo", usuario: null, aviso: null,
    iniciarSesion: vi.fn().mockResolvedValue(undefined),
    registrarse: vi.fn().mockResolvedValue(undefined),
    ...valor,
  };
  render(<ContextoSesion.Provider value={contexto}><Acceso /></ContextoSesion.Provider>);
  return contexto;
}

describe("Acceso", () => {
  test("ingresar manda email y contraseña", async () => {
    const ctx = montar();
    await userEvent.type(screen.getByLabelText("Email"), "ana@x.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "secreto1");
    await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    expect(ctx.iniciarSesion).toHaveBeenCalledWith("ana@x.com", "secreto1");
  });

  test("muestra el error de ingreso en un alert", async () => {
    montar({ iniciarSesion: vi.fn().mockRejectedValue(new Error("Email o contraseña incorrectos.")) });
    await userEvent.type(screen.getByLabelText("Email"), "ana@x.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "mala");
    await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email o contraseña incorrectos.");
  });

  test("muestra el aviso de sesión vencida", () => {
    montar({ aviso: "La sesión venció. Volvé a ingresar." });
    expect(screen.getByRole("status")).toHaveTextContent("La sesión venció. Volvé a ingresar.");
  });

  test("registro: el código de coordinación es opcional y sin él va vacío", async () => {
    const ctx = montar();
    await userEvent.click(screen.getByRole("tab", { name: "Registrarme" }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Ana Gómez");
    await userEvent.type(screen.getByLabelText("Email"), "ana@x.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "secreto1");
    expect(screen.getByLabelText(/Código de coordinación \(opcional\)/)).toHaveValue("");
    await userEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(ctx.registrarse).toHaveBeenCalledWith({ nombre: "Ana Gómez", email: "ana@x.com", password: "secreto1", codigo: "" });
  });

  test("registro con código lo envía", async () => {
    const ctx = montar();
    await userEvent.click(screen.getByRole("tab", { name: "Registrarme" }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Enzo");
    await userEvent.type(screen.getByLabelText("Email"), "enzo@x.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "secreto1");
    await userEvent.type(screen.getByLabelText(/Código de coordinación \(opcional\)/), "SMG");
    await userEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(ctx.registrarse).toHaveBeenCalledWith(expect.objectContaining({ codigo: "SMG" }));
  });

  test("la contraseña exige 6 caracteres en el registro y avisa sin enviar", async () => {
    const ctx = montar();
    await userEvent.click(screen.getByRole("tab", { name: "Registrarme" }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Ana");
    await userEvent.type(screen.getByLabelText("Email"), "ana@x.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "123");
    await userEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(ctx.registrarse).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent("al menos 6 caracteres");
  });

  test("doble clic no envía dos veces: el botón se deshabilita mientras espera", async () => {
    let resolver;
    const iniciarSesion = vi.fn(() => new Promise((r) => { resolver = r; }));
    montar({ iniciarSesion });
    await userEvent.type(screen.getByLabelText("Email"), "ana@x.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "secreto1");
    await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    const enCurso = screen.getByRole("button", { name: "Ingresando…" });
    expect(enCurso).toBeDisabled();
    await userEvent.click(enCurso);
    expect(iniciarSesion).toHaveBeenCalledTimes(1);
    resolver();
    await waitFor(() => expect(screen.getByRole("button", { name: "Ingresar" })).toBeEnabled());
  });
});

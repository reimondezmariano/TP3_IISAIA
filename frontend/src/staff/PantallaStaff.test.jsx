import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import PantallaStaff from "./PantallaStaff.jsx";

const yo = { id: 9, nombre: "Enzo", rol: "COORDINADOR", estado: "ACTIVO" };
const horarioDe = (id, dia, hora, hasta = null) => ({ horarioId: id, diaSemana: dia, horaInicio: hora, duracionHoras: 12, frecuenciaSemanas: 1, fechaAncla: "2026-09-28", vigenteDesde: "2026-09-28", vigenteHasta: hasta });
const USUARIOS = [
  { id: 9, nombre: "Enzo", email: "enzo@x.com", rol: "COORDINADOR", estado: "ACTIVO", fechaBaja: null, horarios: [] },
  { id: 1, nombre: "Ana Gómez", email: "ana@x.com", rol: "MEDICO", estado: "ACTIVO", fechaBaja: null, horarios: [horarioDe(7, 1, "08:00:00")] },
  { id: 2, nombre: "Beto Díaz", email: "beto@x.com", rol: "MEDICO", estado: "PENDIENTE", fechaBaja: null, horarios: [] },
  { id: 3, nombre: "Carla Ruiz", email: "carla@x.com", rol: "MEDICO", estado: "BAJA", fechaBaja: "2026-10-01", horarios: [] },
];
const version = (id, medico, dia, hora, desde = "2026-09-28") => ({ id, medico, diaSemana: dia, horaInicio: hora, duracionHoras: 12, frecuenciaSemanas: 1, fechaAncla: "2026-09-28", vigenteDesde: desde, vigenteHasta: null });
const HORARIOS = [
  { id: 7, estado: "CON_TITULAR", versiones: [version(70, { id: 1, nombre: "Ana Gómez" }, 1, "08:00:00")] },
  { id: 8, estado: "SIN_TITULAR", versiones: [version(80, null, 3, "20:00:00")] },
  { id: 9, estado: "CERRADO", versiones: [{ ...version(90, { id: 1, nombre: "Ana Gómez" }, 5, "08:00:00"), vigenteHasta: "2026-09-01" }] },
];
const AFECTADO = { id: "7:2026-10-12", horarioId: 7, fecha: "2026-10-12", inicio: "2026-10-12T08:00:00-03:00", fin: "2026-10-12T20:00:00-03:00", titular: { id: 1, nombre: "Ana Gómez" }, asignado: null };

function montar({ post = vi.fn(), patch = vi.fn(), usuarios = USUARIOS, horarios = HORARIOS } = {}) {
  const api = {
    get: vi.fn(async (ruta) => {
      if (ruta === "/api/health") return { ahora: "2026-10-08T10:00:00-03:00" };
      if (ruta === "/api/usuarios") return usuarios;
      if (ruta === "/api/horarios") return horarios;
      throw new Error(`no simulada ${ruta}`);
    }),
    post,
    patch,
  };
  render(<PantallaStaff api={api} usuario={yo} />);
  return api;
}
const fila = async (nombre) => {
  await screen.findByText("Staff y horarios");
  return [...document.querySelectorAll("[data-usuario-id]")].find((li) => li.textContent.includes(nombre));
};
const horario = async (id) => {
  await screen.findByText("Staff y horarios");
  return within(document.querySelector(`[data-horario-id="${id}"]`));
};

describe("PantallaStaff", () => {
  test("lista usuarios con rol, estado y horarios", async () => {
    montar();
    const ana = within(await fila("Ana Gómez"));
    expect(ana.getByText("Médico")).toBeVisible();
    expect(ana.getByText("Activo")).toBeVisible();
    expect(ana.getByText("lunes 08:00 · 12 h · todas las semanas")).toBeVisible();
    expect(within(await fila("Carla Ruiz")).getByText("Baja hasta el 2026-10-01")).toBeVisible();
    expect(within(await fila("Enzo")).getByText("(vos)")).toBeVisible();
  });

  test("activar a un pendiente manda PATCH estado ACTIVO y recarga", async () => {
    const patch = vi.fn(async () => ({ usuario: USUARIOS[2], horariosSinTitular: [], turnosAfectados: [], coberturasReabiertas: [] }));
    const api = montar({ patch });
    await userEvent.click(within(await fila("Beto Díaz")).getByRole("button", { name: "Activar" }));
    expect(patch).toHaveBeenCalledWith("/api/usuarios/2", { estado: "ACTIVO" });
    expect(await screen.findByText("Médico activado.")).toBeVisible();
    expect(api.get.mock.calls.filter(([r]) => r === "/api/usuarios")).toHaveLength(2);
  });

  test("solo los pendientes tienen Activar y solo los médicos activos, Dar de baja", async () => {
    montar();
    expect(within(await fila("Ana Gómez")).queryByRole("button", { name: "Activar" })).toBeNull();
    expect(within(await fila("Ana Gómez")).getByRole("button", { name: "Dar de baja" })).toBeVisible();
    expect(within(await fila("Beto Díaz")).queryByRole("button", { name: "Dar de baja" })).toBeNull();
    expect(within(await fila("Carla Ruiz")).queryByRole("button")).toBeNull();
    expect(within(await fila("Enzo")).queryByRole("button", { name: /Pasar a/ })).toBeNull();
  });

  test("cambiar el rol pide confirmación, manda el rol y muestra lo reabierto", async () => {
    const patch = vi.fn(async () => ({ usuario: USUARIOS[1], horariosSinTitular: [7], turnosAfectados: [], coberturasReabiertas: [AFECTADO] }));
    montar({ patch });
    await userEvent.click(within(await fila("Ana Gómez")).getByRole("button", { name: "Pasar a coordinador" }));
    expect(patch).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirmar" }));
    expect(patch).toHaveBeenCalledWith("/api/usuarios/1", { rol: "COORDINADOR" });
    expect(await screen.findByText("Rol cambiado a coordinador.")).toBeVisible();
    expect(screen.getByText("1 horario quedó sin titular (BAJA).")).toBeVisible();
    expect(screen.getByText(/Coberturas que se reabren como vacantes \(1\)/)).toBeVisible();
  });

  test("dar de baja manda la fecha elegida", async () => {
    const post = vi.fn(async () => ({ usuario: USUARIOS[1], horariosSinTitular: [7], turnosAfectados: [AFECTADO], coberturasReabiertas: [] }));
    montar({ post });
    await userEvent.click(within(await fila("Ana Gómez")).getByRole("button", { name: "Dar de baja" }));
    expect(screen.getByLabelText("Último día activo")).toHaveValue("2026-10-08");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar baja" }));
    expect(post).toHaveBeenCalledWith("/api/usuarios/1/baja", { fechaBaja: "2026-10-08" });
    expect(await screen.findByText("Baja registrada.")).toBeVisible();
    expect(screen.getByText(/Turnos ya guardados que cambian \(1\)/)).toBeVisible();
  });

  test("un error del servidor se muestra en la fila", async () => {
    const patch = vi.fn().mockRejectedValue(new ErrorApi(409, "YA_ACTIVO", "El usuario ya está activo."));
    montar({ patch });
    await userEvent.click(within(await fila("Beto Díaz")).getByRole("button", { name: "Activar" }));
    expect(await within(await fila("Beto Díaz")).findByRole("alert")).toHaveTextContent("El usuario ya está activo.");
  });

  test("los horarios sin titular (BAJA) permiten designar uno nuevo desde mañana", async () => {
    const post = vi.fn(async () => ({ version: {}, turnosAfectados: [AFECTADO] }));
    montar({ post });
    const seccion = within((await screen.findByRole("heading", { name: /Horarios sin titular/ })).closest("section"));
    expect(seccion.getByText(/miércoles 20:00/)).toBeVisible();
    expect(seccion.getByLabelText("Desde")).toHaveValue("2026-10-09");
    await userEvent.selectOptions(seccion.getByLabelText("Nuevo titular"), "1");
    await userEvent.click(seccion.getByRole("button", { name: "Designar titular" }));
    expect(post).toHaveBeenCalledWith("/api/horarios/8/versiones", { desde: "2026-10-09", medicoId: 1 });
    expect(await screen.findByText("Nuevo titular designado.")).toBeVisible();
    expect(screen.getByText(/Turnos ya guardados que cambian \(1\)/)).toBeVisible();
  });

  test("solo se ofrecen médicos activos como titular", async () => {
    montar();
    const seccion = within((await screen.findByRole("heading", { name: /Horarios sin titular/ })).closest("section"));
    const opciones = seccion.getAllByRole("option").map((o) => o.textContent);
    expect(opciones).toEqual(["Elegí un médico", "Ana Gómez"]);
  });

  test("modificar un horario manda solo los campos cambiados y muestra los turnos afectados", async () => {
    const post = vi.fn(async () => ({ version: {}, turnosAfectados: [AFECTADO] }));
    montar({ post });
    const li = await horario(7);
    await userEvent.click(li.getByRole("button", { name: "Modificar" }));
    await userEvent.clear(li.getByLabelText("Duración (horas)"));
    await userEvent.type(li.getByLabelText("Duración (horas)"), "8");
    await userEvent.click(li.getByRole("button", { name: "Guardar cambio" }));
    expect(post).toHaveBeenCalledWith("/api/horarios/7/versiones", { desde: "2026-10-09", duracionHoras: 8 });
    expect(await screen.findByText("Horario modificado.")).toBeVisible();
  });

  test("modificar sin cambiar nada no llama al servidor", async () => {
    const post = vi.fn();
    montar({ post });
    const li = await horario(7);
    await userEvent.click(li.getByRole("button", { name: "Modificar" }));
    await userEvent.click(li.getByRole("button", { name: "Guardar cambio" }));
    expect(await li.findByRole("alert")).toHaveTextContent("No cambiaste nada.");
    expect(post).not.toHaveBeenCalled();
  });

  test("cargar un horario nuevo manda el alta", async () => {
    const post = vi.fn(async () => ({ id: 20, estado: "CON_TITULAR", versiones: [] }));
    montar({ post });
    await userEvent.click(await screen.findByRole("button", { name: "Cargar horario nuevo" }));
    await userEvent.click(screen.getByRole("button", { name: "Cargar horario" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Elegí el médico titular.");
    await userEvent.selectOptions(screen.getByLabelText("Médico titular"), "1");
    await userEvent.selectOptions(screen.getByLabelText("Día"), "5");
    await userEvent.clear(screen.getByLabelText(/Frecuencia/));
    await userEvent.type(screen.getByLabelText(/Frecuencia/), "2");
    await userEvent.click(screen.getByRole("button", { name: "Cargar horario" }));
    expect(post).toHaveBeenCalledWith("/api/horarios", { medicoId: 1, diaSemana: 5, horaInicio: "08:00", duracionHoras: 12, frecuenciaSemanas: 2, vigenteDesde: "2026-10-09" });
    expect(await screen.findByText("Horario cargado.")).toBeVisible();
  });

  test("los horarios cerrados no se pueden modificar", async () => {
    montar();
    await screen.findByText("Staff y horarios");
    expect(document.querySelector('[data-horario-id="9"]')).toBeNull();
  });

  test("si no se puede cargar, error y Reintentar", async () => {
    const api = { get: vi.fn(async (r) => { if (r === "/api/health") return { ahora: "2026-10-08T10:00:00-03:00" }; throw new ErrorApi(403, "SIN_PERMISO", "Solo coordinadores."); }) };
    render(<PantallaStaff api={api} usuario={yo} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Solo coordinadores.");
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeVisible();
  });
});

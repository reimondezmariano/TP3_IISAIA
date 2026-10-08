import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import DetalleTurno from "./DetalleTurno.jsx";

const turno = {
  id: "7:2026-10-12", horarioId: 7, fecha: "2026-10-12",
  inicio: "2026-10-12T08:00:00-03:00", fin: "2026-10-12T16:00:00-03:00", duracionHoras: 8,
  titular: { id: 3, nombre: "Carlos Ruiz" },
};
const estadoBase = { tipo: "NORMAL", etiqueta: null, urgente: false, postulantes: [], postulado: false, acciones: [] };
const acciones = () => ({ avisarAusencia: vi.fn(async () => {}), retirarAviso: vi.fn(async () => {}), postularme: vi.fn(), retirarPostulacion: vi.fn() });
const montar = (estado, acc = acciones(), onCerrar = vi.fn()) => {
  render(<DetalleTurno turno={turno} estado={{ ...estadoBase, ...estado }} acciones={acc} onCerrar={onCerrar} />);
  return { acc, onCerrar };
};

describe("DetalleTurno", () => {
  test("rotula como simuladas solo las postulaciones", () => {
    montar({ acciones: ["POSTULARME"] });
    expect(screen.getByTestId("rotulo-simulado")).toHaveTextContent("postulaciones");
  });

  test("avisar o retirar la ausencia no lleva el rótulo de simulado", () => {
    montar({ acciones: ["AVISAR_AUSENCIA"] });
    expect(screen.queryByTestId("rotulo-simulado")).toBeNull();
  });

  test("si el servidor rechaza el aviso, se muestra su mensaje y se conserva el motivo", async () => {
    const acc = acciones();
    acc.avisarAusencia.mockRejectedValue(new Error("El turno ya empezó: no se puede generar una vacante."));
    montar({ acciones: ["AVISAR_AUSENCIA"] }, acc);
    await userEvent.type(screen.getByLabelText(/Motivo/), "Congreso");
    await userEvent.click(screen.getByRole("button", { name: "Avisar ausencia" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El turno ya empezó");
    expect(screen.getByLabelText(/Motivo/)).toHaveValue("Congreso");
  });

  test("si el servidor rechaza el retiro, se muestra su mensaje", async () => {
    const acc = acciones();
    acc.retirarAviso.mockRejectedValue(new Error("La vacante ya no está abierta."));
    montar({ acciones: ["RETIRAR_AVISO"] }, acc);
    await userEvent.click(screen.getByRole("button", { name: "Retirar aviso" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("ya no está abierta");
  });

  test("Avisar ausencia pide motivo (visible solo para coordinadores) y lo manda", async () => {
    const { acc } = montar({ acciones: ["AVISAR_AUSENCIA"] });
    expect(screen.getByText(/solo lo ven los coordinadores/i)).toBeVisible();
    await userEvent.type(screen.getByLabelText(/Motivo/), "Congreso");
    await userEvent.click(screen.getByRole("button", { name: "Avisar ausencia" }));
    expect(acc.avisarAusencia).toHaveBeenCalledWith("7:2026-10-12", "Congreso");
  });

  test("el motivo es obligatorio", async () => {
    const { acc } = montar({ acciones: ["AVISAR_AUSENCIA"] });
    await userEvent.click(screen.getByRole("button", { name: "Avisar ausencia" }));
    expect(acc.avisarAusencia).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Escribí el motivo");
  });

  test.each([
    ["RETIRAR_AVISO", "Retirar aviso", "retirarAviso"],
    ["POSTULARME", "Postularme", "postularme"],
    ["RETIRAR_POSTULACION", "Retirar postulación", "retirarPostulacion"],
  ])("acción %s", async (accion, texto, funcion) => {
    const { acc } = montar({ acciones: [accion] });
    await userEvent.click(screen.getByRole("button", { name: texto }));
    expect(acc[funcion]).toHaveBeenCalledWith("7:2026-10-12");
  });

  test("sin acciones no hay botones de acción", () => {
    montar({ acciones: [] });
    expect(screen.queryByRole("button", { name: /Avisar|Postularme|Retirar/ })).toBeNull();
  });

  test("lista postulantes y marca urgente", () => {
    montar({ tipo: "VACANTE", etiqueta: "Vacante urgente", urgente: true, postulantes: [{ id: -1, nombre: "Florencia" }] });
    expect(screen.getByText("Florencia")).toBeVisible();
    expect(screen.getByText("Vacante urgente")).toBeVisible();
  });

  test("cerrar", async () => {
    const { onCerrar } = montar({});
    await userEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(onCerrar).toHaveBeenCalled();
  });
});

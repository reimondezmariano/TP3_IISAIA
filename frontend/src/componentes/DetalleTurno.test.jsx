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
const acciones = () => ({ avisarAusencia: vi.fn(), retirarAviso: vi.fn(), postularme: vi.fn(), retirarPostulacion: vi.fn() });
const montar = (estado, acc = acciones(), onCerrar = vi.fn()) => {
  render(<DetalleTurno turno={turno} estado={{ ...estadoBase, ...estado }} acciones={acc} onCerrar={onCerrar} />);
  return { acc, onCerrar };
};

describe("DetalleTurno", () => {
  test("rotula que las acciones son simuladas", () => {
    montar({});
    expect(screen.getByTestId("rotulo-simulado")).toHaveTextContent("Simulado");
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

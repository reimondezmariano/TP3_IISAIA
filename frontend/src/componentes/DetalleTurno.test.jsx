import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import DetalleTurno from "./DetalleTurno.jsx";

const turno = {
  id: "7:2026-10-12", horarioId: 7, fecha: "2026-10-12",
  inicio: "2026-10-12T08:00:00-03:00", fin: "2026-10-12T16:00:00-03:00", duracionHoras: 8,
  titular: { id: 3, nombre: "Carlos Ruiz" },
  vacante: { id: 12, urgente: false, generadaPor: { id: 3, nombre: "Carlos Ruiz" } },
};
const estadoBase = { tipo: "NORMAL", etiqueta: null, urgente: false, postulado: false, acciones: [] };
const acciones = () => ({ avisarAusencia: vi.fn(async () => {}), retirarAviso: vi.fn(async () => {}), postularme: vi.fn(async () => {}), retirarPostulacion: vi.fn(async () => {}) });
const montar = (estado, acc = acciones(), onCerrar = vi.fn(), panel = null, datosTurno = {}) => {
  render(<DetalleTurno turno={{ ...turno, ...datosTurno }} estado={{ ...estadoBase, ...estado }} acciones={acc} panel={panel} onCerrar={onCerrar} />);
  return { acc, onCerrar };
};

describe("DetalleTurno", () => {
  test("con asignado: muestra a quien cubre y al titular como dato secundario", () => {
    montar({}, acciones(), vi.fn(), null, { titular: { id: 3, nombre: "Mariano Reimondez" }, asignado: { id: 4, nombre: "Carlos Lugones" } });
    expect(screen.getByText("Carlos Lugones, cubre a Mariano Reimondez")).toBeVisible();
  });

  test("con asignado y titular en BAJA: cubre por baja del titular", () => {
    montar({}, acciones(), vi.fn(), null, { titular: null, asignado: { id: 4, nombre: "Carlos Lugones" } });
    expect(screen.getByText("Carlos Lugones, cubre por baja del titular")).toBeVisible();
  });

  test("ya no hay rótulo de simulado: las postulaciones son reales", () => {
    montar({ acciones: ["POSTULARME"] });
    expect(screen.queryByTestId("rotulo-simulado")).toBeNull();
  });

  test("si el servidor rechaza la postulación, se muestra su mensaje", async () => {
    const acc = acciones();
    acc.postularme.mockRejectedValue(new Error("El turno no tiene una vacante abierta."));
    montar({ acciones: ["POSTULARME"] }, acc);
    await userEvent.click(screen.getByRole("button", { name: "Postularme" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("no tiene una vacante abierta");
  });

  test("retirar la postulación usa el miPostulacionId del turno", async () => {
    const acc = acciones();
    montar({ acciones: ["RETIRAR_POSTULACION"] }, acc, vi.fn(), null, { miPostulacionId: 31 });
    await userEvent.click(screen.getByRole("button", { name: "Retirar postulación" }));
    expect(acc.retirarPostulacion).toHaveBeenCalledWith(31);
  });

  test("si el servidor rechaza el retiro de la postulación, se muestra su mensaje", async () => {
    const acc = acciones();
    acc.retirarPostulacion.mockRejectedValue(new Error("La postulación ya estaba retirada."));
    montar({ acciones: ["RETIRAR_POSTULACION"] }, acc);
    await userEvent.click(screen.getByRole("button", { name: "Retirar postulación" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("ya estaba retirada");
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

  test("postularme usa el id del turno", async () => {
    const { acc } = montar({ acciones: ["POSTULARME"] });
    await userEvent.click(screen.getByRole("button", { name: "Postularme" }));
    expect(acc.postularme).toHaveBeenCalledWith("7:2026-10-12");
  });

  test("retirar el aviso usa el id de la vacante que informa el turno", async () => {
    const { acc } = montar({ acciones: ["RETIRAR_AVISO"] });
    await userEvent.click(screen.getByRole("button", { name: "Retirar aviso" }));
    expect(acc.retirarAviso).toHaveBeenCalledWith(12);
  });

  test("coordinador: generar vacante pide motivo y llama a la misma acción", async () => {
    const { acc } = montar({ acciones: ["GENERAR_VACANTE"] });
    await userEvent.click(screen.getByRole("button", { name: "Generar vacante" }));
    expect(acc.avisarAusencia).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Escribí el motivo");
    await userEvent.type(screen.getByLabelText(/Motivo/), "Licencia");
    await userEvent.click(screen.getByRole("button", { name: "Generar vacante" }));
    expect(acc.avisarAusencia).toHaveBeenCalledWith("7:2026-10-12", "Licencia");
    expect(screen.queryByRole("button", { name: "Avisar ausencia" })).toBeNull();
  });

  test("coordinador: retirar la vacante usa el id del turno", async () => {
    const { acc } = montar({ acciones: ["RETIRAR_VACANTE"] });
    await userEvent.click(screen.getByRole("button", { name: "Retirar vacante" }));
    expect(acc.retirarAviso).toHaveBeenCalledWith(12);
  });

  test("muestra quién generó la vacante y el panel de coordinación si lo hay", () => {
    montar({ tipo: "VACANTE", etiqueta: "Vacante", acciones: [] }, acciones(), vi.fn(), <p>Panel de prueba</p>);
    expect(screen.getByText(/Generada por Carlos Ruiz/)).toBeVisible();
    expect(screen.getByText("Panel de prueba")).toBeVisible();
  });

  test("sin acciones no hay botones de acción", () => {
    montar({ acciones: [] });
    expect(screen.queryByRole("button", { name: /Avisar|Postularme|Retirar/ })).toBeNull();
  });

  test("marca la vacante urgente", () => {
    montar({ tipo: "VACANTE", etiqueta: "Vacante urgente", urgente: true });
    expect(screen.getByText("Vacante urgente")).toBeVisible();
  });

  test("cerrar", async () => {
    const { onCerrar } = montar({});
    await userEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(onCerrar).toHaveBeenCalled();
  });
});

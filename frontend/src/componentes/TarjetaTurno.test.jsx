import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import TarjetaTurno from "./TarjetaTurno.jsx";

const turno = {
  id: "7:2026-10-10", horarioId: 7, fecha: "2026-10-10",
  inicio: "2026-10-10T08:00:00-03:00", fin: "2026-10-10T16:00:00-03:00", duracionHoras: 8,
  titular: { id: 3, nombre: "Carlos Ruiz" },
};
const usuario = { id: 1, nombre: "Ana", rol: "MEDICO" };

describe("TarjetaTurno", () => {
  test("muestra horario, duración y titular", () => {
    render(<TarjetaTurno turno={turno} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.getByText("08:00 – 16:00")).toBeVisible();
    expect(screen.getByText("8 h")).toBeVisible();
    expect(screen.getByText("Carlos Ruiz")).toBeVisible();
  });

  test("marca 'Mi guardia' cuando el titular soy yo", () => {
    render(<TarjetaTurno turno={{ ...turno, titular: { id: 1, nombre: "Ana" } }} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.getByText("Mi guardia")).toBeVisible();
  });

  test("turno que termina otro día: indica el día siguiente", () => {
    const nocturno = { ...turno, inicio: "2026-10-10T20:00:00-03:00", fin: "2026-10-11T08:00:00-03:00", duracionHoras: 12 };
    render(<TarjetaTurno turno={nocturno} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.getByText("20:00 – 08:00 (+1 día)")).toBeVisible();
  });

  test("24 horas: termina a la misma hora del día siguiente", () => {
    const largo = { ...turno, inicio: "2026-10-10T08:00:00-03:00", fin: "2026-10-11T08:00:00-03:00", duracionHoras: 24 };
    render(<TarjetaTurno turno={largo} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.getByText("08:00 – 08:00 (+1 día)")).toBeVisible();
  });

  test("titular null: etiqueta BAJA (D24), sin romper", () => {
    render(<TarjetaTurno turno={{ ...turno, titular: null }} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.getByText("BAJA")).toBeVisible();
    expect(screen.getByText("Sin titular")).toBeVisible();
  });

  test("semáforo: color según la vacante que trae GET /api/turnos (D08)", () => {
    const { rerender } = render(<TarjetaTurno turno={{ ...turno, vacante: null }} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.getByTestId("turno")).toHaveAttribute("data-semaforo", "cubierta");
    const vacante = { id: 12, urgente: false, generadaPor: { id: 3, nombre: "Carlos Ruiz" } };
    rerender(<TarjetaTurno turno={{ ...turno, vacante }} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.getByTestId("turno")).toHaveAttribute("data-semaforo", "vacante");
    expect(screen.getByText("Vacante")).toBeVisible();
    rerender(<TarjetaTurno turno={{ ...turno, vacante: { ...vacante, urgente: true } }} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.getByTestId("turno")).toHaveAttribute("data-semaforo", "urgente");
    expect(screen.getByText("Vacante urgente")).toBeVisible();
    rerender(<TarjetaTurno turno={{ ...turno, titular: null }} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.getByTestId("turno")).toHaveAttribute("data-semaforo", "baja");
  });

  test("con asignado: muestra a quien cubre y al titular como dato secundario", () => {
    const asignado = { id: 4, nombre: "Carlos Lugones" };
    const { rerender } = render(<TarjetaTurno turno={{ ...turno, titular: { id: 3, nombre: "Mariano Reimondez" }, asignado }} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.getByText("Carlos Lugones")).toBeVisible();
    expect(screen.getByText("cubre a Mariano Reimondez")).toBeVisible();
    rerender(<TarjetaTurno turno={{ ...turno, titular: null, asignado }} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.getByText("cubre por baja del titular")).toBeVisible();
  });

  test("D34: BAJA con postulantes va en ámbar con la etiqueta BAJA y la cantidad; toda tarjeta con postulantes la muestra", () => {
    const { rerender } = render(<TarjetaTurno turno={{ ...turno, titular: null, cantidadPostulantes: 2 }} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.getByTestId("turno")).toHaveAttribute("data-semaforo", "baja-postulantes");
    expect(screen.getByText("BAJA")).toBeVisible();
    expect(screen.getByText("2 postulantes")).toBeVisible();
    rerender(<TarjetaTurno turno={{ ...turno, cantidadPostulantes: 1, vacante: { id: 1, urgente: false, generadaPor: { id: 3, nombre: "Carlos Ruiz" } } }} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.getByText("1 postulante")).toBeVisible();
    rerender(<TarjetaTurno turno={{ ...turno, cantidadPostulantes: 0 }} usuario={usuario} onAbrir={vi.fn()} />);
    expect(screen.queryByText(/postulante/)).toBeNull();
  });

  test("clic abre el detalle con el turno", async () => {
    const onAbrir = vi.fn();
    render(<TarjetaTurno turno={turno} usuario={usuario} onAbrir={onAbrir} />);
    await userEvent.click(screen.getByRole("button"));
    expect(onAbrir).toHaveBeenCalledWith(turno);
  });
});

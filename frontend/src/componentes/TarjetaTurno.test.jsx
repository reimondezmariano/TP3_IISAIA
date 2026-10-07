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
    render(<TarjetaTurno turno={turno} usuario={usuario} estado={null} onAbrir={vi.fn()} />);
    expect(screen.getByText("08:00 – 16:00")).toBeVisible();
    expect(screen.getByText("8 h")).toBeVisible();
    expect(screen.getByText("Carlos Ruiz")).toBeVisible();
  });

  test("marca 'Mi guardia' cuando el titular soy yo", () => {
    render(<TarjetaTurno turno={{ ...turno, titular: { id: 1, nombre: "Ana" } }} usuario={usuario} estado={null} onAbrir={vi.fn()} />);
    expect(screen.getByText("Mi guardia")).toBeVisible();
  });

  test("turno que termina otro día: indica el día siguiente", () => {
    const nocturno = { ...turno, inicio: "2026-10-10T20:00:00-03:00", fin: "2026-10-11T08:00:00-03:00", duracionHoras: 12 };
    render(<TarjetaTurno turno={nocturno} usuario={usuario} estado={null} onAbrir={vi.fn()} />);
    expect(screen.getByText("20:00 – 08:00 (+1 día)")).toBeVisible();
  });

  test("24 horas: termina a la misma hora del día siguiente", () => {
    const largo = { ...turno, inicio: "2026-10-10T08:00:00-03:00", fin: "2026-10-11T08:00:00-03:00", duracionHoras: 24 };
    render(<TarjetaTurno turno={largo} usuario={usuario} estado={null} onAbrir={vi.fn()} />);
    expect(screen.getByText("08:00 – 08:00 (+1 día)")).toBeVisible();
  });

  test("titular null: etiqueta BAJA (D24), sin romper", () => {
    render(<TarjetaTurno turno={{ ...turno, titular: null }} usuario={usuario} estado={null} onAbrir={vi.fn()} />);
    expect(screen.getByText("BAJA")).toBeVisible();
    expect(screen.getByText("Sin titular")).toBeVisible();
  });

  test("clic abre el detalle con el turno", async () => {
    const onAbrir = vi.fn();
    render(<TarjetaTurno turno={turno} usuario={usuario} estado={null} onAbrir={onAbrir} />);
    await userEvent.click(screen.getByRole("button"));
    expect(onAbrir).toHaveBeenCalledWith(turno);
  });
});

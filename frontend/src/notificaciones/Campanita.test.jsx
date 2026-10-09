import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import AvisoUrgente from "./AvisoUrgente.jsx";
import Campanita from "./Campanita.jsx";

const n = (id, leidaEn = null) => ({ id, tipo: "TURNO_ASIGNADO", mensaje: `Mensaje ${id}`, creadaEn: "2026-10-08T10:00:00-03:00", leidaEn });
const estado = (lista, extra = {}) => ({
  lista, noLeidas: lista.filter((x) => !x.leidaEn).length, urgentes: [], marcarLeida: vi.fn(async () => {}), marcarTodas: vi.fn(async () => {}), descartarUrgente: vi.fn(), ...extra,
});

describe("Campanita", () => {
  test("muestra el contador de no leídas", () => {
    render(<Campanita notificaciones={estado([n(1), n(2), n(3, "2026-10-08T11:00:00-03:00")])} />);
    expect(screen.getByTestId("contador-notificaciones")).toHaveTextContent("2");
    expect(screen.getByRole("button", { name: "Notificaciones, 2 sin leer" })).toBeVisible();
  });

  test("sin no leídas no hay contador", () => {
    render(<Campanita notificaciones={estado([n(1, "2026-10-08T11:00:00-03:00")])} />);
    expect(screen.queryByTestId("contador-notificaciones")).toBeNull();
  });

  test("abre la lista y marca una como leída", async () => {
    const notificaciones = estado([n(1), n(2)]);
    render(<Campanita notificaciones={notificaciones} />);
    await userEvent.click(screen.getByRole("button", { name: /Notificaciones/ }));
    expect(screen.getByText("Mensaje 1")).toBeVisible();
    await userEvent.click(screen.getAllByRole("button", { name: "Marcar leída" })[0]);
    expect(notificaciones.marcarLeida).toHaveBeenCalledWith(1);
  });

  test("marca todas como leídas", async () => {
    const notificaciones = estado([n(1), n(2)]);
    render(<Campanita notificaciones={notificaciones} />);
    await userEvent.click(screen.getByRole("button", { name: /Notificaciones/ }));
    await userEvent.click(screen.getByRole("button", { name: "Marcar todas como leídas" }));
    expect(notificaciones.marcarTodas).toHaveBeenCalled();
  });

  test("NUEVO_REGISTRO: al tocarla lleva a la pantalla de staff y la marca leída", async () => {
    const nueva = { id: 9, tipo: "NUEVO_REGISTRO", mensaje: "Ana Gómez se registró y espera activación", creadaEn: "2026-10-08T10:00:00-03:00", leidaEn: null };
    const notificaciones = estado([nueva]);
    const onIr = vi.fn();
    render(<Campanita notificaciones={notificaciones} onIr={onIr} />);
    await userEvent.click(screen.getByRole("button", { name: /Notificaciones/ }));
    await userEvent.click(screen.getByRole("button", { name: "Ana Gómez se registró y espera activación" }));
    expect(onIr).toHaveBeenCalledWith("staff");
    expect(notificaciones.marcarLeida).toHaveBeenCalledWith(9);
    expect(screen.queryByRole("region", { name: "Lista de notificaciones" })).toBeNull();
  });

  test("las demás notificaciones no navegan", async () => {
    const onIr = vi.fn();
    render(<Campanita notificaciones={estado([n(1)])} onIr={onIr} />);
    await userEvent.click(screen.getByRole("button", { name: /Notificaciones/ }));
    expect(screen.queryByRole("button", { name: "Mensaje 1" })).toBeNull();
    expect(onIr).not.toHaveBeenCalled();
  });

  test("lista vacía", async () => {
    render(<Campanita notificaciones={estado([])} />);
    await userEvent.click(screen.getByRole("button", { name: "Notificaciones" }));
    expect(screen.getByText("No tenés notificaciones.")).toBeVisible();
  });

  test("si marcar falla, muestra el error", async () => {
    const notificaciones = estado([n(1)], { marcarLeida: vi.fn().mockRejectedValue(new Error("No existe.")) });
    render(<Campanita notificaciones={notificaciones} />);
    await userEvent.click(screen.getByRole("button", { name: /Notificaciones/ }));
    await userEvent.click(screen.getByRole("button", { name: "Marcar leída" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No existe.");
  });
});

describe("AvisoUrgente", () => {
  test("sin urgentes no muestra nada", () => {
    const { container } = render(<AvisoUrgente notificaciones={estado([])} />);
    expect(container).toBeEmptyDOMElement();
  });

  test("muestra la urgente y 'Entendido' la marca como leída", async () => {
    const urgente = { ...n(7), tipo: "VACANTE_URGENTE", mensaje: "Vacante urgente el sábado" };
    const notificaciones = estado([urgente], { urgentes: [urgente] });
    render(<AvisoUrgente notificaciones={notificaciones} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Vacante urgente el sábado");
    await userEvent.click(screen.getByRole("button", { name: "Entendido" }));
    expect(notificaciones.marcarLeida).toHaveBeenCalledWith(7);
  });

  test("si no se pudo marcar, se descarta el aviso emergente y se muestra el error", async () => {
    const urgente = { ...n(7), tipo: "VACANTE_URGENTE", mensaje: "Urgente" };
    const notificaciones = estado([urgente], { urgentes: [urgente], marcarLeida: vi.fn().mockRejectedValue(new Error("Sin conexión.")) });
    render(<AvisoUrgente notificaciones={notificaciones} />);
    await userEvent.click(screen.getByRole("button", { name: "Entendido" }));
    expect(notificaciones.descartarUrgente).toHaveBeenCalledWith(7);
  });
});

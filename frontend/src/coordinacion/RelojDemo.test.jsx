import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import RelojDemo from "./RelojDemo.jsx";

const AHORA = "2026-10-09T10:00:00-03:00";
const modoDemo = (extra = {}) => ({
  post: vi.fn(async (ruta, cuerpo) => {
    if (!("ahora" in cuerpo)) throw new ErrorApi(422, "VALIDACION", "Falta ahora.");
    return { ahora: cuerpo.ahora ?? "2026-10-09T09:00:00-03:00", desfaseHoras: 0 };
  }),
  ...extra,
});

describe("RelojDemo", () => {
  test("sin modo demo (la ruta responde 404) el control no aparece", async () => {
    const api = { post: vi.fn().mockRejectedValue(new ErrorApi(404, "NO_ENCONTRADO", "Not Found")) };
    const { container } = render(<RelojDemo api={api} ahora={AHORA} onCambio={vi.fn()} />);
    await vi.waitFor(() => expect(api.post).toHaveBeenCalledWith("/api/demo/reloj", {}));
    expect(container).toBeEmptyDOMElement();
  });

  test("si la consulta falla por otra causa tampoco aparece", async () => {
    const api = { post: vi.fn().mockRejectedValue(new ErrorApi(0, "SIN_CONEXION", "Sin conexión.")) };
    const { container } = render(<RelojDemo api={api} ahora={AHORA} onCambio={vi.fn()} />);
    await vi.waitFor(() => expect(api.post).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  test("con modo demo muestra +1 hora, +1 día y volver a la hora real; el sondeo no cambia el reloj", async () => {
    const api = modoDemo();
    render(<RelojDemo api={api} ahora={AHORA} onCambio={vi.fn()} />);
    expect(await screen.findByRole("button", { name: "+1 hora" })).toBeVisible();
    expect(screen.getByRole("button", { name: "+1 día" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Volver a la hora real" })).toBeVisible();
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(api.post).toHaveBeenCalledWith("/api/demo/reloj", {});
  });

  test("+1 hora y +1 día mandan el nuevo instante y avisan para recargar", async () => {
    const api = modoDemo();
    const onCambio = vi.fn(async () => {});
    render(<RelojDemo api={api} ahora={AHORA} onCambio={onCambio} />);
    await userEvent.click(await screen.findByRole("button", { name: "+1 hora" }));
    expect(api.post).toHaveBeenLastCalledWith("/api/demo/reloj", { ahora: "2026-10-09T14:00:00.000Z" });
    expect(onCambio).toHaveBeenCalledWith("2026-10-09T14:00:00.000Z");
    await userEvent.click(screen.getByRole("button", { name: "+1 día" }));
    expect(api.post).toHaveBeenLastCalledWith("/api/demo/reloj", { ahora: "2026-10-10T13:00:00.000Z" });
  });

  test("volver a la hora real manda ahora null", async () => {
    const api = modoDemo();
    const onCambio = vi.fn(async () => {});
    render(<RelojDemo api={api} ahora={AHORA} onCambio={onCambio} />);
    await userEvent.click(await screen.findByRole("button", { name: "Volver a la hora real" }));
    expect(api.post).toHaveBeenLastCalledWith("/api/demo/reloj", { ahora: null });
    expect(onCambio).toHaveBeenCalled();
  });

  test("si el servidor rechaza el cambio, muestra su mensaje y no recarga", async () => {
    const api = modoDemo();
    const onCambio = vi.fn();
    render(<RelojDemo api={api} ahora={AHORA} onCambio={onCambio} />);
    const boton = await screen.findByRole("button", { name: "Volver a la hora real" });
    api.post.mockRejectedValueOnce(new ErrorApi(409, "REINICIAR_DEMO", "Reiniciá la demo."));
    await userEvent.click(boton);
    expect(await screen.findByRole("alert")).toHaveTextContent("Reiniciá la demo.");
    expect(onCambio).not.toHaveBeenCalled();
  });
});

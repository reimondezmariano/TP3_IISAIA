import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import { ContextoSesion } from "../sesion/useSesion.js";
import Calendario from "./Calendario.jsx";

const turno = (horarioId, fecha, hi, hf, titular, finFecha = fecha) => ({
  id: `${horarioId}:${fecha}`, horarioId, fecha,
  inicio: `${fecha}T${hi}:00-03:00`, fin: `${finFecha}T${hf}:00-03:00`, duracionHoras: 8, titular,
});
const SEMANA_ACTUAL = [
  turno(1, "2026-10-05", "08:00", "16:00", { id: 1, nombre: "Ana" }),
  turno(2, "2026-10-07", "20:00", "08:00", { id: 3, nombre: "Carlos" }, "2026-10-08"),
  turno(3, "2026-10-11", "20:00", "08:00", null, "2026-10-12"),
];

function montar({ turnosPorDesde = {}, post = vi.fn(async () => ({})), health = { ahora: "2026-10-07T10:00:00-03:00" }, usuario = { id: 1, nombre: "Ana", rol: "MEDICO", estado: "ACTIVO" } } = {}) {
  const api = {
    post,
    get: vi.fn(async (ruta, consulta) => {
      if (ruta === "/api/health") {
        if (health instanceof Error) throw health;
        return health;
      }
      return turnosPorDesde[consulta.desde] ?? [];
    }),
  };
  render(
    <ContextoSesion.Provider value={{ api, usuario, estado: "activo", recargar: vi.fn(), cerrarSesion: vi.fn() }}>
      <Calendario />
    </ContextoSesion.Provider>,
  );
  return api;
}

describe("Calendario", () => {
  test("arranca en la semana de 'ahora' del servidor (lunes a domingo) y muestra los turnos en su día", async () => {
    const api = montar({ turnosPorDesde: { "2026-10-05": SEMANA_ACTUAL } });
    expect(await screen.findByText("5 al 11 de octubre de 2026")).toBeVisible();
    expect(await screen.findAllByTestId("turno")).toHaveLength(3);
    expect(api.get).toHaveBeenCalledWith("/api/turnos", { desde: "2026-10-05", hasta: "2026-10-11" });
    expect(document.querySelectorAll("[data-fecha]")).toHaveLength(7);
    expect(within(document.querySelector('[data-fecha="2026-10-05"]')).getAllByTestId("turno")).toHaveLength(1);
    expect(within(document.querySelector('[data-fecha="2026-10-07"]')).getByText("20:00 – 08:00 (+1 día)")).toBeVisible();
    expect(within(document.querySelector('[data-fecha="2026-10-11"]')).getByText("BAJA")).toBeVisible();
  });

  test("muestra la leyenda del semáforo arriba del calendario (D08)", async () => {
    montar({ turnosPorDesde: { "2026-10-05": SEMANA_ACTUAL } });
    const leyenda = await screen.findByRole("list", { name: "Colores del calendario" });
    for (const nombre of ["Cubierta", "Vacante abierta", "Vacante urgente", "BAJA (sin titular)"]) {
      expect(within(leyenda).getByText(nombre)).toBeVisible();
    }
  });

  test("resalta el día de hoy según el servidor", async () => {
    montar({ turnosPorDesde: { "2026-10-05": SEMANA_ACTUAL } });
    await screen.findAllByTestId("turno");
    expect(document.querySelector('[data-fecha="2026-10-07"]')).toHaveAttribute("aria-current", "date");
  });

  test("si /health falla, usa la hora del navegador y sigue andando", async () => {
    montar({ health: new Error("caído") });
    expect(await screen.findByRole("heading", { level: 2 })).toBeVisible();
  });

  test("navega a la semana siguiente, a la anterior y vuelve a hoy", async () => {
    const api = montar({ turnosPorDesde: { "2026-10-12": [turno(9, "2026-10-12", "08:00", "14:00", { id: 3, nombre: "Carlos" })] } });
    await screen.findByText("5 al 11 de octubre de 2026");
    await userEvent.click(screen.getByRole("button", { name: "Semana siguiente" }));
    expect(await screen.findByText("12 al 18 de octubre de 2026")).toBeVisible();
    expect(api.get).toHaveBeenCalledWith("/api/turnos", { desde: "2026-10-12", hasta: "2026-10-18" });
    expect(await screen.findByText("Carlos")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Hoy" }));
    expect(await screen.findByText("5 al 11 de octubre de 2026")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Semana anterior" }));
    expect(await screen.findByText("28 de septiembre al 4 de octubre de 2026")).toBeVisible();
  });

  test("semana sin turnos: estado vacío", async () => {
    montar();
    expect(await screen.findByText("No hay guardias esta semana.")).toBeVisible();
  });

  test("si la API devuelve solo un turno de la semana anterior que se solapa, la semana se ve vacía", async () => {
    const dePasada = turno(8, "2026-10-04", "20:00", "08:00", { id: 3, nombre: "Carlos" }, "2026-10-05");
    montar({ turnosPorDesde: { "2026-10-05": [dePasada] } });
    expect(await screen.findByText("No hay guardias esta semana.")).toBeVisible();
    expect(screen.queryByTestId("turno")).toBeNull();
  });

  test("error del servidor: mensaje y Reintentar", async () => {
    const api = montar();
    await screen.findByText("No hay guardias esta semana.");
    api.get.mockRejectedValueOnce(new ErrorApi(0, "SIN_CONEXION", "No se pudo conectar con el servidor."));
    await userEvent.click(screen.getByRole("button", { name: "Semana siguiente" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo conectar con el servidor.");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("No hay guardias esta semana.")).toBeVisible();
  });

  test("cerrar sesión", async () => {
    const cerrarSesion = vi.fn();
    render(
      <ContextoSesion.Provider value={{ api: { get: vi.fn().mockResolvedValue([]) }, usuario: { id: 1, nombre: "Ana", rol: "MEDICO" }, estado: "activo", recargar: vi.fn(), cerrarSesion }}>
        <Calendario />
      </ContextoSesion.Provider>,
    );
    await userEvent.click(await screen.findByRole("button", { name: "Cerrar sesión" }));
    expect(cerrarSesion).toHaveBeenCalled();
  });
});

describe("Calendario con ausencias", () => {
  const propio = turno(1, "2026-10-09", "08:00", "16:00", { id: 1, nombre: "Ana" });

  beforeEach(() => window.localStorage.clear());

  test("avisar la ausencia llama a la API y marca el turno como vacante; retirar la saca", async () => {
    const post = vi.fn(async (ruta) => (ruta.endsWith("/vacantes") ? { id: 12, turnoId: "1:2026-10-09" } : { id: 12 }));
    montar({ turnosPorDesde: { "2026-10-05": [propio] }, post });
    await userEvent.click(await screen.findByTestId("turno"));
    await userEvent.type(screen.getByLabelText(/Motivo/), "Congreso");
    await userEvent.click(screen.getByRole("button", { name: "Avisar ausencia" }));
    expect(post).toHaveBeenCalledWith("/api/turnos/1:2026-10-09/vacantes", { motivo: "Congreso" });
    await userEvent.click(await screen.findByRole("button", { name: "Retirar aviso" }));
    expect(post).toHaveBeenCalledWith("/api/vacantes/12/retiro");
    expect(await screen.findByRole("button", { name: "Avisar ausencia" })).toBeVisible();
  });

  test("después de avisar la ausencia vuelve a pedir la semana para actualizar el semáforo", async () => {
    const post = vi.fn(async () => ({ id: 12, turnoId: "1:2026-10-09" }));
    const api = montar({ turnosPorDesde: { "2026-10-05": [propio] }, post });
    await userEvent.click(await screen.findByTestId("turno"));
    const pedidosTurnos = () => api.get.mock.calls.filter(([ruta]) => ruta === "/api/turnos").length;
    const antes = pedidosTurnos();
    await userEvent.type(screen.getByLabelText(/Motivo/), "Congreso");
    await userEvent.click(screen.getByRole("button", { name: "Avisar ausencia" }));
    await vi.waitFor(() => expect(pedidosTurnos()).toBe(antes + 1));
    expect(screen.getByTestId("turno")).toBeVisible();
  });

  test("si el servidor rechaza el aviso, el turno sigue sin vacante y se ve el error", async () => {
    const post = vi.fn().mockRejectedValue(new ErrorApi(409, "TURNO_YA_EMPEZO", "El turno ya empezó: no se puede generar una vacante."));
    montar({ turnosPorDesde: { "2026-10-05": [propio] }, post });
    await userEvent.click(await screen.findByTestId("turno"));
    await userEvent.type(screen.getByLabelText(/Motivo/), "Congreso");
    await userEvent.click(screen.getByRole("button", { name: "Avisar ausencia" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El turno ya empezó");
    expect(screen.queryByRole("button", { name: "Retirar aviso" })).toBeNull();
  });

  test("el coordinador no ve botones de acción en el detalle", async () => {
    montar({
      usuario: { id: 9, nombre: "Enzo", rol: "COORDINADOR", estado: "ACTIVO" },
      turnosPorDesde: { "2026-10-05": [turno(1, "2026-10-09", "08:00", "16:00", null)] },
    });
    await userEvent.click(await screen.findByTestId("turno"));
    expect(screen.getByRole("dialog")).toBeVisible();
    expect(screen.queryByRole("button", { name: /^(Postularme|Avisar ausencia)$/ })).toBeNull();
  });

  test("cambiar de semana cierra el detalle", async () => {
    montar({ turnosPorDesde: { "2026-10-05": [propio] } });
    await userEvent.click(await screen.findByTestId("turno"));
    await userEvent.click(screen.getByRole("button", { name: "Semana siguiente" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

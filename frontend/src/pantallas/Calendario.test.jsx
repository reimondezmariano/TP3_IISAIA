import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { ErrorApi } from "../lib/api.js";
import { ContextoSesion } from "../sesion/useSesion.js";
import Calendario from "./Calendario.jsx";

const turno = (horarioId, fecha, hi, hf, titular, finFecha = fecha) => ({
  id: `${horarioId}:${fecha}`, horarioId, fecha,
  inicio: `${fecha}T${hi}:00-03:00`, fin: `${finFecha}T${hf}:00-03:00`, duracionHoras: 8, titular, vacante: null,
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
      const turnos = turnosPorDesde[consulta.desde];
      return typeof turnos === "function" ? turnos() : turnos ?? [];
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
    for (const nombre of ["Cubierta", "Vacante abierta", "Vacante urgente", "BAJA (sin titular)", "BAJA con postulantes"]) {
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
  const conVacante = { ...propio, vacante: { id: 12, urgente: false, generadaPor: { id: 1, nombre: "Ana" } } };

  test("avisar la ausencia llama a la API, recarga los turnos y muestra Retirar aviso con el id del servidor", async () => {
    let turnos = [propio];
    const post = vi.fn(async (ruta) => {
      if (ruta.endsWith("/vacantes")) turnos = [conVacante];
      if (ruta.endsWith("/retiro")) turnos = [propio];
      return { id: 12 };
    });
    montar({ turnosPorDesde: { "2026-10-05": () => turnos }, post });
    await userEvent.click(await screen.findByTestId("turno"));
    await userEvent.type(screen.getByLabelText(/Motivo/), "Congreso");
    await userEvent.click(screen.getByRole("button", { name: "Avisar ausencia" }));
    expect(post).toHaveBeenCalledWith("/api/turnos/1:2026-10-09/vacantes", { motivo: "Congreso" });
    await userEvent.click(await screen.findByRole("button", { name: "Retirar aviso" }));
    expect(post).toHaveBeenCalledWith("/api/vacantes/12/retiro");
    expect(await screen.findByRole("button", { name: "Avisar ausencia" })).toBeVisible();
  });

  test("la vacante abierta viene del servidor: se puede retirar sin haberla generado en este navegador", async () => {
    const post = vi.fn(async () => ({ id: 12 }));
    montar({ turnosPorDesde: { "2026-10-05": [conVacante] }, post });
    await userEvent.click(await screen.findByTestId("turno"));
    await userEvent.click(screen.getByRole("button", { name: "Retirar aviso" }));
    expect(post).toHaveBeenCalledWith("/api/vacantes/12/retiro");
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

  test("el coordinador genera la vacante de un turno ajeno y puede retirarla; nunca ve acciones de médico", async () => {
    const ajeno = turno(1, "2026-10-09", "08:00", "16:00", { id: 3, nombre: "Carlos" });
    const conVacanteAjena = { ...ajeno, vacante: { id: 30, urgente: false, generadaPor: { id: 3, nombre: "Carlos" } } };
    let turnos = [ajeno];
    const post = vi.fn(async (ruta) => {
      if (ruta.endsWith("/vacantes")) turnos = [conVacanteAjena];
      if (ruta.endsWith("/retiro")) turnos = [ajeno];
      return { id: 30 };
    });
    montar({ usuario: { id: 9, nombre: "Enzo", rol: "COORDINADOR", estado: "ACTIVO" }, turnosPorDesde: { "2026-10-05": () => turnos }, post });
    await userEvent.click(await screen.findByTestId("turno"));
    expect(screen.queryByRole("button", { name: /^(Postularme|Avisar ausencia|Retirar aviso)$/ })).toBeNull();
    await userEvent.type(screen.getByLabelText(/Motivo/), "Licencia");
    await userEvent.click(screen.getByRole("button", { name: "Generar vacante" }));
    expect(post).toHaveBeenCalledWith("/api/turnos/1:2026-10-09/vacantes", { motivo: "Licencia" });
    await userEvent.click(await screen.findByRole("button", { name: "Retirar vacante" }));
    expect(post).toHaveBeenCalledWith("/api/vacantes/30/retiro");
    expect(await screen.findByRole("button", { name: "Generar vacante" })).toBeVisible();
  });

  test("cambiar de semana cierra el detalle", async () => {
    montar({ turnosPorDesde: { "2026-10-05": [propio] } });
    await userEvent.click(await screen.findByTestId("turno"));
    await userEvent.click(screen.getByRole("button", { name: "Semana siguiente" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("Calendario del coordinador: panel de cobertura", () => {
  const coordinador = { id: 9, nombre: "Enzo", rol: "COORDINADOR", estado: "ACTIVO" };
  const ajeno = turno(1, "2026-10-09", "08:00", "16:00", { id: 3, nombre: "Carlos" });

  test("no pide candidatos para un turno normal sin vacante", async () => {
    const api = montar({ usuario: coordinador, turnosPorDesde: { "2026-10-05": [ajeno] } });
    await userEvent.click(await screen.findByTestId("turno"));
    expect(screen.queryByRole("region", { name: "Cobertura del turno" })).toBeNull();
    expect(api.get).not.toHaveBeenCalledWith(expect.stringContaining("/candidatos"));
  });

  test("con vacante abierta muestra el panel de cobertura", async () => {
    const conVacante = { ...ajeno, vacante: { id: 30, urgente: false, generadaPor: { id: 3, nombre: "Carlos" } } };
    montar({ usuario: coordinador, turnosPorDesde: { "2026-10-05": [conVacante] } });
    await userEvent.click(await screen.findByTestId("turno"));
    expect(await screen.findByRole("region", { name: "Cobertura del turno" })).toBeVisible();
  });

  describe("vista mensual", () => {
    const MES = [
      turno(1, "2026-10-01", "08:00", "16:00", { id: 1, nombre: "Ana" }),
      { ...turno(2, "2026-10-20", "20:00", "08:00", { id: 3, nombre: "Carlos" }, "2026-10-21"), vacante: { id: 5, urgente: true, generadaPor: { id: 3, nombre: "Carlos" } } },
      turno(3, "2026-10-31", "08:00", "16:00", null),
    ];

    async function abrirMes(extra = {}) {
      const api = montar({ turnosPorDesde: { "2026-10-05": SEMANA_ACTUAL, "2026-09-28": MES, ...extra } });
      await screen.findByText("5 al 11 de octubre de 2026");
      await userEvent.click(screen.getByRole("button", { name: "Mes" }));
      return api;
    }

    test("pide la grilla completa del mes y muestra cada guardia en su día con el color del semáforo", async () => {
      const api = await abrirMes();
      expect(await screen.findByText("octubre de 2026", { selector: "h2" })).toBeVisible();
      expect(api.get).toHaveBeenCalledWith("/api/turnos", { desde: "2026-09-28", hasta: "2026-11-01" });
      const chips = await screen.findAllByTestId("turno-mes");
      expect(chips).toHaveLength(3);
      expect(within(document.querySelector('[data-fecha="2026-10-20"]')).getByTestId("turno-mes")).toHaveAttribute("data-semaforo", "urgente");
      expect(within(document.querySelector('[data-fecha="2026-10-31"]')).getByTestId("turno-mes")).toHaveAttribute("data-semaforo", "baja");
      expect(document.querySelectorAll(".mes-dia")).toHaveLength(35);
    });

    test("tocar una guardia abre el mismo detalle", async () => {
      await abrirMes();
      await userEvent.click((await screen.findAllByTestId("turno-mes"))[0]);
      expect(await screen.findByRole("dialog", { name: "Detalle de la guardia" })).toBeVisible();
    });

    test("mes anterior, siguiente y selector de mes y año", async () => {
      const api = await abrirMes();
      await screen.findAllByTestId("turno-mes");
      await userEvent.click(screen.getByRole("button", { name: "Mes siguiente" }));
      expect(await screen.findByText("noviembre de 2026", { selector: "h2" })).toBeVisible();
      expect(api.get).toHaveBeenCalledWith("/api/turnos", { desde: "2026-10-26", hasta: "2026-12-06" });
      await userEvent.click(screen.getByRole("button", { name: "Mes anterior" }));
      await userEvent.click(screen.getByRole("button", { name: "Mes anterior" }));
      expect(await screen.findByText("septiembre de 2026", { selector: "h2" })).toBeVisible();
      await userEvent.selectOptions(screen.getByRole("combobox", { name: "Año" }), "2027");
      await userEvent.selectOptions(screen.getByRole("combobox", { name: "Mes" }), "2");
      expect(await screen.findByText("febrero de 2027", { selector: "h2" })).toBeVisible();
      expect(api.get).toHaveBeenCalledWith("/api/turnos", { desde: "2027-02-01", hasta: "2027-02-28" });
      await userEvent.click(screen.getByRole("button", { name: "Hoy" }));
      expect(await screen.findByText("octubre de 2026", { selector: "h2" })).toBeVisible();
    });

    test("se puede volver a la vista semanal", async () => {
      await abrirMes();
      await userEvent.click(screen.getByRole("button", { name: "Semana" }));
      expect(await screen.findByText("5 al 11 de octubre de 2026")).toBeVisible();
    });
  });

  describe("reloj de demo", () => {
    const coordinador = { id: 9, nombre: "Enzo", rol: "COORDINADOR", estado: "ACTIVO" };

    test("con la ruta disponible adelanta el reloj y recarga el calendario con el nuevo 'hoy'", async () => {
      const post = vi.fn(async (ruta, cuerpo) => {
        if (ruta === "/api/demo/reloj") {
          if (!("ahora" in cuerpo)) throw new ErrorApi(422, "VALIDACION", "Falta ahora.");
          return { ahora: cuerpo.ahora, desfaseHoras: 24 };
        }
        return {};
      });
      const api = montar({ turnosPorDesde: { "2026-10-05": SEMANA_ACTUAL }, post, usuario: coordinador });
      await userEvent.click(await screen.findByRole("button", { name: "+1 día" }));
      expect(post).toHaveBeenLastCalledWith("/api/demo/reloj", { ahora: "2026-10-08T13:00:00.000Z" });
      await vi.waitFor(() => expect(document.querySelector('[data-fecha="2026-10-08"]')).toHaveAttribute("aria-current", "date"));
      expect(api.get.mock.calls.filter(([ruta]) => ruta === "/api/turnos").length).toBeGreaterThan(1);
    });

    test("sin modo demo (404) el coordinador no ve el control", async () => {
      const post = vi.fn().mockRejectedValue(new ErrorApi(404, "NO_ENCONTRADO", "Not Found"));
      montar({ turnosPorDesde: { "2026-10-05": SEMANA_ACTUAL }, post, usuario: coordinador });
      await screen.findAllByTestId("turno");
      await vi.waitFor(() => expect(post).toHaveBeenCalledWith("/api/demo/reloj", {}));
      expect(screen.queryByRole("button", { name: "+1 hora" })).toBeNull();
    });

    test("el médico nunca ve el control ni consulta la ruta", async () => {
      const post = vi.fn(async () => ({}));
      montar({ turnosPorDesde: { "2026-10-05": SEMANA_ACTUAL }, post });
      await screen.findAllByTestId("turno");
      expect(screen.queryByRole("button", { name: "+1 hora" })).toBeNull();
      expect(post).not.toHaveBeenCalled();
    });
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { crearAuthFalso, sesionFalsa } from "../pruebas/auth-falso.js";
import { SesionProvider } from "./SesionProvider.jsx";
import { useSesion } from "./useSesion.js";

const json = (status, cuerpo) =>
  new Response(JSON.stringify(cuerpo), { status, headers: { "Content-Type": "application/json" } });
const ME_ACTIVO = { id: 1, nombre: "Ana", email: "ana@x.com", rol: "MEDICO", estado: "ACTIVO" };

function Sonda() {
  const s = useSesion();
  return (
    <div>
      <p data-testid="estado">{s.estado}</p>
      <p data-testid="nombre">{s.usuario?.nombre ?? ""}</p>
      <p data-testid="aviso">{s.aviso ?? ""}</p>
      <p data-testid="sugerido">{s.nombreSugerido}</p>
      <button onClick={() => s.iniciarSesion("ana@x.com", "secreto1").catch((e) => (document.title = e.message))}>entrar</button>
      <button onClick={() => s.registrarse({ nombre: "Ana", email: "ana@x.com", password: "secreto1", codigo: "SMG" })}>registrar</button>
      <button onClick={() => s.completarRegistro({ nombre: "Ana", codigo: "" })}>completar</button>
      <button onClick={() => s.cerrarSesion()}>salir</button>
    </div>
  );
}

function montar({ auth, rutas }) {
  const fetchImpl = vi.fn(async (url, opciones) => {
    const manejador = rutas[`${opciones.method} ${url}`];
    if (!manejador) throw new Error(`Ruta no simulada: ${opciones.method} ${url}`);
    return manejador(opciones);
  });
  render(
    <SesionProvider auth={auth} fetchImpl={fetchImpl}>
      <Sonda />
    </SesionProvider>,
  );
  return { fetchImpl };
}

const estadoEs = (texto) => waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent(texto));

describe("SesionProvider", () => {
  test("sin sesión de Supabase: anónimo y no llama a la API", async () => {
    const { fetchImpl } = montar({ auth: crearAuthFalso(), rutas: {} });
    await estadoEs("anonimo");
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test("con sesión, pide /api/me con Bearer y queda activo", async () => {
    const { fetchImpl } = montar({
      auth: crearAuthFalso({ sesion: sesionFalsa() }),
      rutas: { "GET /api/me": () => json(200, ME_ACTIVO) },
    });
    await estadoEs("activo");
    expect(screen.getByTestId("nombre")).toHaveTextContent("Ana");
    expect(fetchImpl.mock.calls[0][1].headers.Authorization).toBe("Bearer tok-ana@x.com");
  });

  test.each([
    ["PENDIENTE", "pendiente"],
    ["BAJA", "baja"],
  ])("usuario %s -> estado %s", async (estadoApi, esperado) => {
    montar({
      auth: crearAuthFalso({ sesion: sesionFalsa() }),
      rutas: { "GET /api/me": () => json(200, { ...ME_ACTIVO, estado: estadoApi }) },
    });
    await estadoEs(esperado);
  });

  test("cuenta de Supabase sin Usuario (403 USUARIO_NO_REGISTRADO) -> sin-registro", async () => {
    montar({
      auth: crearAuthFalso({ sesion: sesionFalsa() }),
      rutas: { "GET /api/me": () => json(403, { codigo: "USUARIO_NO_REGISTRADO", mensaje: "Falta registro." }) },
    });
    await estadoEs("sin-registro");
  });

  test("token vencido: cierra la sesión de Supabase y vuelve a anónimo con el aviso", async () => {
    const auth = crearAuthFalso({ sesion: sesionFalsa() });
    montar({
      auth,
      rutas: { "GET /api/me": () => json(401, { codigo: "TOKEN_VENCIDO", mensaje: "La sesión venció. Volvé a ingresar." }) },
    });
    await estadoEs("anonimo");
    expect(auth.signOut).toHaveBeenCalled();
    await waitFor(() => expect(screen.getByTestId("aviso")).toHaveTextContent("La sesión venció. Volvé a ingresar."));
  });

  test("servidor caído: estado error con aviso", async () => {
    montar({
      auth: crearAuthFalso({ sesion: sesionFalsa() }),
      rutas: { "GET /api/me": () => { throw new TypeError("Failed to fetch"); } },
    });
    await estadoEs("error");
    expect(screen.getByTestId("aviso")).toHaveTextContent("No se pudo conectar con el servidor");
  });

  test("login: signInWithPassword y luego /api/me", async () => {
    const auth = crearAuthFalso();
    montar({ auth, rutas: { "GET /api/me": () => json(200, ME_ACTIVO) } });
    await estadoEs("anonimo");
    await userEvent.click(screen.getByText("entrar"));
    await estadoEs("activo");
    expect(auth.signInWithPassword).toHaveBeenCalledWith({ email: "ana@x.com", password: "secreto1" });
  });

  test("login con credenciales malas lanza el mensaje traducido y queda anónimo", async () => {
    const auth = crearAuthFalso();
    auth.signInWithPassword.mockResolvedValueOnce({ data: { session: null }, error: { code: "invalid_credentials", message: "Invalid login credentials" } });
    montar({ auth, rutas: {} });
    await estadoEs("anonimo");
    await userEvent.click(screen.getByText("entrar"));
    await waitFor(() => expect(document.title).toBe("Email o contraseña incorrectos."));
    expect(screen.getByTestId("estado")).toHaveTextContent("anonimo");
  });

  test("registro con código: signUp, POST /api/registro con codigoCoordinacion y un solo /api/me después", async () => {
    const llamadas = [];
    const auth = crearAuthFalso();
    montar({
      auth,
      rutas: {
        "POST /api/registro": (opciones) => {
          llamadas.push(["registro", JSON.parse(opciones.body)]);
          return json(201, { ...ME_ACTIVO, rol: "COORDINADOR" });
        },
        "GET /api/me": () => {
          llamadas.push(["me"]);
          return json(200, { ...ME_ACTIVO, rol: "COORDINADOR" });
        },
      },
    });
    await estadoEs("anonimo");
    await userEvent.click(screen.getByText("registrar"));
    await estadoEs("activo");
    expect(auth.signUp).toHaveBeenCalledWith(expect.objectContaining({ email: "ana@x.com", password: "secreto1" }));
    expect(llamadas[0]).toEqual(["registro", { nombre: "Ana", codigoCoordinacion: "SMG" }]);
    expect(llamadas.filter(([n]) => n === "me")).toHaveLength(1);
  });

  test("código incorrecto: la cuenta de Supabase queda y la app pasa a sin-registro con el mensaje", async () => {
    const auth = crearAuthFalso();
    montar({
      auth,
      rutas: {
        "POST /api/registro": () => json(422, { codigo: "CODIGO_INVALIDO", mensaje: "El código de coordinación no es correcto." }),
        "GET /api/me": () => json(403, { codigo: "USUARIO_NO_REGISTRADO", mensaje: "Falta registro." }),
      },
    });
    await estadoEs("anonimo");
    await userEvent.click(screen.getByText("registrar"));
    await estadoEs("sin-registro");
    expect(screen.getByTestId("aviso")).toHaveTextContent("El código de coordinación no es correcto.");
    expect(auth.signOut).not.toHaveBeenCalled();
  });

  test("completarRegistro manda solo el nombre cuando no hay código", async () => {
    const cuerpos = [];
    let primera = true;
    montar({
      auth: crearAuthFalso({ sesion: sesionFalsa() }),
      rutas: {
        "GET /api/me": () => {
          if (primera) {
            primera = false;
            return json(403, { codigo: "USUARIO_NO_REGISTRADO", mensaje: "x" });
          }
          return json(200, { ...ME_ACTIVO, estado: "PENDIENTE" });
        },
        "POST /api/registro": (opciones) => {
          cuerpos.push(JSON.parse(opciones.body));
          return json(201, ME_ACTIVO);
        },
      },
    });
    await estadoEs("sin-registro");
    await userEvent.click(screen.getByText("completar"));
    await estadoEs("pendiente");
    expect(cuerpos).toEqual([{ nombre: "Ana" }]);
  });

  test("cerrar sesión vuelve a anónimo", async () => {
    const auth = crearAuthFalso({ sesion: sesionFalsa() });
    montar({ auth, rutas: { "GET /api/me": () => json(200, ME_ACTIVO) } });
    await estadoEs("activo");
    await userEvent.click(screen.getByText("salir"));
    await estadoEs("anonimo");
    expect(screen.getByTestId("nombre")).toHaveTextContent("");
  });

  test("sin registro en Guardia Viva: ofrece el nombre que quedó en la cuenta de Supabase", async () => {
    const auth = crearAuthFalso({ sesion: { ...sesionFalsa(), user: { email: "ana@x.com", user_metadata: { nombre: "Ana Gómez" } } } });
    montar({
      auth,
      rutas: { "GET /api/me": async () => json(404, { codigo: "USUARIO_NO_REGISTRADO", mensaje: "Falta el registro." }) },
    });
    await estadoEs("sin-registro");
    expect(screen.getByTestId("sugerido")).toHaveTextContent("Ana Gómez");
  });
});

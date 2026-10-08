import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { crearClienteApi, ErrorApi } from "../lib/api.js";
import { traducirErrorAuth } from "../lib/errores-auth.js";
import { ContextoSesion } from "./useSesion.js";

const ESTADO_DE_CUENTA = { ACTIVO: "activo", PENDIENTE: "pendiente", BAJA: "baja" };

export function SesionProvider({ auth, fetchImpl, children }) {
  const [estado, setEstado] = useState("cargando");
  const [usuario, setUsuario] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [nombreSugerido, setNombreSugerido] = useState("");
  const registrando = useRef(false);
  // Evita que varios 401 simultáneos cierren la sesión dos veces.
  const cerrandoPorToken = useRef(false);

  const cerrarPorTokenInvalido = useCallback(
    async (error) => {
      if (cerrandoPorToken.current) return;
      cerrandoPorToken.current = true;
      try {
        await auth.signOut();
      } finally {
        cerrandoPorToken.current = false;
        setUsuario(null);
        setAviso(error.message);
        setEstado("anonimo");
      }
    },
    [auth],
  );

  const api = useMemo(
    () =>
      crearClienteApi({
        obtenerToken: async () => (await auth.getSession()).data.session?.access_token ?? null,
        alSesionInvalida: cerrarPorTokenInvalido,
        fetchImpl,
      }),
    [auth, fetchImpl, cerrarPorTokenInvalido],
  );

  const cargarUsuario = useCallback(async () => {
    const { data } = await auth.getSession();
    if (!data.session) {
      setUsuario(null);
      setEstado("anonimo");
      return;
    }
    try {
      const yo = await api.get("/api/me");
      setUsuario(yo);
      setAviso(null);
      setEstado(ESTADO_DE_CUENTA[yo.estado] ?? "error");
    } catch (error) {
      if (!(error instanceof ErrorApi)) throw error;
      if (error.codigo === "USUARIO_NO_REGISTRADO") {
        setUsuario(null);
        // El nombre que la persona escribió al crear la cuenta queda en Supabase: se vuelve a ofrecer.
        const nombre = data.session.user?.user_metadata?.nombre;
        setNombreSugerido(typeof nombre === "string" ? nombre : "");
        setEstado("sin-registro");
      } else if (error.status === 401) {
        // api.js ya avisó a cerrarPorTokenInvalido
      } else {
        setUsuario(null);
        setAviso(error.message);
        setEstado("error");
      }
    }
  }, [auth, api]);

  useEffect(() => {
    cargarUsuario();
    const { data } = auth.onAuthStateChange((evento, sesion) => {
      if (registrando.current) return; // el registro en curso carga el usuario al terminar
      if (evento === "SIGNED_OUT" || !sesion) {
        setUsuario(null);
        setEstado("anonimo");
      } else if (evento === "SIGNED_IN") {
        cargarUsuario();
      }
    });
    return () => data.subscription.unsubscribe();
  }, [auth, cargarUsuario]);

  const iniciarSesion = useCallback(
    async (email, password) => {
      const { error } = await auth.signInWithPassword({ email, password });
      if (error) throw new Error(traducirErrorAuth(error));
      setAviso(null);
    },
    [auth],
  );

  const enviarRegistro = useCallback(
    async (nombre, codigo) => {
      const cuerpo = { nombre: nombre.trim() };
      if (codigo?.trim()) cuerpo.codigoCoordinacion = codigo.trim();
      await api.post("/api/registro", cuerpo);
    },
    [api],
  );

  const registrarse = useCallback(
    async ({ nombre, email, password, codigo }) => {
      registrando.current = true;
      try {
        const { data, error } = await auth.signUp({ email, password, options: { data: { nombre } } });
        if (error) throw new Error(traducirErrorAuth(error));
        if (!data.session) {
          throw new Error("Tu cuenta se creó pero Supabase pide confirmar el email antes de ingresar. Avisale al equipo.");
        }
        try {
          await enviarRegistro(nombre, codigo);
          setAviso(null);
        } catch (errorRegistro) {
          if (!(errorRegistro instanceof ErrorApi)) throw errorRegistro;
          if (errorRegistro.status !== 401) setAviso(errorRegistro.message);
        }
      } finally {
        registrando.current = false;
      }
      await cargarUsuario();
    },
    [auth, enviarRegistro, cargarUsuario],
  );

  const completarRegistro = useCallback(
    async ({ nombre, codigo }) => {
      try {
        await enviarRegistro(nombre, codigo);
      } catch (error) {
        if (error instanceof ErrorApi && error.status !== 401) throw new Error(error.message);
        throw error;
      }
      setAviso(null);
      await cargarUsuario();
    },
    [enviarRegistro, cargarUsuario],
  );

  const cerrarSesion = useCallback(async () => {
    await auth.signOut();
    setUsuario(null);
    setAviso(null);
    setEstado("anonimo");
  }, [auth]);

  const valor = useMemo(
    () => ({ estado, usuario, aviso, nombreSugerido, api, iniciarSesion, registrarse, completarRegistro, recargar: cargarUsuario, cerrarSesion }),
    [estado, usuario, aviso, nombreSugerido, api, iniciarSesion, registrarse, completarRegistro, cargarUsuario, cerrarSesion],
  );

  return <ContextoSesion.Provider value={valor}>{children}</ContextoSesion.Provider>;
}

export const CODIGOS_SESION_INVALIDA = ["SIN_SESION", "TOKEN_VENCIDO", "TOKEN_INVALIDO"];

export class ErrorApi extends Error {
  constructor(status, codigo, mensaje) {
    super(mensaje);
    this.name = "ErrorApi";
    this.status = status;
    this.codigo = codigo;
  }
}

function conConsulta(ruta, consulta) {
  const parametros = new URLSearchParams();
  for (const [clave, valor] of Object.entries(consulta ?? {})) {
    if (valor !== undefined && valor !== null) parametros.set(clave, String(valor));
  }
  const texto = parametros.toString();
  return texto ? `${ruta}?${texto}` : ruta;
}

export function crearClienteApi({ obtenerToken, alSesionInvalida = () => {}, fetchImpl = (...args) => fetch(...args) }) {
  async function pedir(metodo, ruta, { consulta, cuerpo } = {}) {
    const token = await obtenerToken();
    if (!token) {
      const error = new ErrorApi(401, "SIN_SESION", "Falta el token de sesión.");
      alSesionInvalida(error);
      throw error;
    }
    const headers = { Authorization: `Bearer ${token}` };
    if (cuerpo !== undefined) headers["Content-Type"] = "application/json";

    let respuesta;
    try {
      respuesta = await fetchImpl(conConsulta(ruta, consulta), {
        method: metodo,
        headers,
        body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
      });
    } catch {
      throw new ErrorApi(0, "SIN_CONEXION", "No se pudo conectar con el servidor. Revisá tu conexión.");
    }

    if (respuesta.status === 204) return undefined;
    const datos = await respuesta.json().catch(() => null);
    if (!respuesta.ok) {
      const error = new ErrorApi(
        respuesta.status,
        datos?.codigo ?? `HTTP_${respuesta.status}`,
        datos?.mensaje ?? `El servidor respondió con error ${respuesta.status}.`,
      );
      if (respuesta.status === 401 && CODIGOS_SESION_INVALIDA.includes(error.codigo)) alSesionInvalida(error);
      throw error;
    }
    return datos ?? undefined;
  }

  return {
    get: (ruta, consulta) => pedir("GET", ruta, { consulta }),
    post: (ruta, cuerpo) => pedir("POST", ruta, { cuerpo }),
    put: (ruta, cuerpo) => pedir("PUT", ruta, { cuerpo }),
    patch: (ruta, cuerpo) => pedir("PATCH", ruta, { cuerpo }),
  };
}

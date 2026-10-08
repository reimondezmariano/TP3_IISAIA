// DATOS SIMULADOS: hasta que existan los endpoints de vacantes y postulaciones (D15, D16), el estado de
// cada turno se deriva acá. Cuando existan, esta carpeta se reemplaza por llamadas a la API.
import { horasHasta, terminoAntes } from "../lib/fechas.js";

const POSTULANTE_SIMULADO = { id: -1, nombre: "Florencia" };

export function hashTurno(turnoId) {
  let h = 0;
  for (let i = 0; i < turnoId.length; i++) h = (h * 31 + turnoId.charCodeAt(i)) >>> 0;
  return h;
}

export function derivarEstado({ turno, usuario, ahora, override }) {
  if (terminoAntes(turno, ahora)) {
    return { tipo: "PASADO", etiqueta: null, urgente: false, postulantes: [], postulado: false, acciones: [] };
  }

  const esCoordinador = usuario.rol === "COORDINADOR";
  const sinTitular = turno.titular === null;
  const mio = !sinTitular && turno.titular.id === usuario.id;
  const hash = hashTurno(turno.id);

  let vacante;
  if (sinTitular) vacante = true;
  else if (mio) vacante = Boolean(override?.vacante);
  else vacante = hash % 5 === 0;

  const postulado = !mio && Boolean(override?.postulado);
  const postulantes = [];
  if (!mio && !sinTitular && vacante && hash % 10 === 0) postulantes.push(POSTULANTE_SIMULADO);
  if (postulado) postulantes.push({ id: usuario.id, nombre: usuario.nombre });

  const horas = horasHasta(turno, ahora);
  const urgente = vacante && !sinTitular && horas >= 0 && horas < 24;

  let acciones = [];
  if (!esCoordinador) {
    if (mio) acciones = [vacante ? "RETIRAR_AVISO" : "AVISAR_AUSENCIA"];
    else if (vacante) acciones = [postulado ? "RETIRAR_POSTULACION" : "POSTULARME"];
  }

  let tipo = "NORMAL";
  let etiqueta = null;
  if (sinTitular) {
    tipo = "BAJA";
    etiqueta = "BAJA";
  } else if (vacante) {
    tipo = "VACANTE";
    etiqueta = urgente ? "Vacante urgente" : "Vacante";
  }

  return { tipo, etiqueta, urgente, postulantes, postulado, acciones };
}

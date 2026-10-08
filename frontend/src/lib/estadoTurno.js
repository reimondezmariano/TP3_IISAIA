// Estado de un turno para el usuario que mira: etiqueta, urgencia y acciones disponibles. Usa solo datos del
// servidor: el titular, el asignado, mi postulación activa, la vacante abierta que informa `GET /turnos` (`turno.vacante`, null si no hay) y el
// reloj del servidor (D27). El servidor tiene la última palabra: si una acción no corresponde, la rechaza.
import { horasHasta, terminoAntes } from "./fechas.js";

export function derivarEstado({ turno, usuario, ahora }) {
  const vacio = { tipo: "NORMAL", etiqueta: null, urgente: false, postulado: false, acciones: [] };
  if (terminoAntes(turno, ahora)) return { ...vacio, tipo: "PASADO" };

  const vacante = turno.vacante ?? null;
  const sinTitular = turno.titular === null;
  const postulado = (turno.miPostulacionId ?? null) !== null;
  // Avisa la ausencia el titular o el asignado vigente (D15, D31).
  const mio = (!sinTitular && turno.titular.id === usuario.id) || turno.asignado?.id === usuario.id;
  const esCoordinador = usuario.rol === "COORDINADOR";
  const empezado = horasHasta(turno, ahora) < 0;
  const urgente = vacante !== null && vacante.urgente && !empezado;
  const estado = {
    ...vacio,
    tipo: sinTitular ? "BAJA" : vacante ? "VACANTE" : "NORMAL",
    etiqueta: sinTitular ? "BAJA" : vacante ? (urgente ? "Vacante urgente" : "Vacante") : null,
    urgente,
  };

  if (esCoordinador) {
    // Generan la vacante el titular, el asignado o un coordinador; la retiran quien la generó o un coordinador (D15).
    let acciones = [];
    if (vacante) acciones = ["RETIRAR_VACANTE"];
    else if (!sinTitular && !empezado) acciones = ["GENERAR_VACANTE"];
    return { ...estado, acciones };
  }

  if (mio) {
    let acciones;
    if (!vacante) acciones = empezado ? [] : ["AVISAR_AUSENCIA"];
    else acciones = vacante.generadaPor.id === usuario.id ? ["RETIRAR_AVISO"] : [];
    return { ...estado, acciones };
  }

  let acciones = [];
  if (postulado) acciones = ["RETIRAR_POSTULACION"];
  else if (!empezado && (vacante || sinTitular)) acciones = ["POSTULARME"];
  return { ...estado, postulado, acciones };
}

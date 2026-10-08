// Estado de un turno para el usuario que mira: etiqueta, urgencia y acciones disponibles. Solo usa datos reales:
// el titular del turno, las vacantes y postulaciones propias y el reloj del servidor (D27). El servidor tiene la
// última palabra: si una acción no corresponde (por ejemplo, el turno no tiene vacante), la rechaza.
import { horasHasta, terminoAntes } from "./fechas.js";

export function derivarEstado({ turno, usuario, ahora, vacanteAbierta = false, postulado = false }) {
  const vacio = { tipo: "NORMAL", etiqueta: null, urgente: false, postulado: false, acciones: [] };
  if (terminoAntes(turno, ahora)) return { ...vacio, tipo: "PASADO" };

  const sinTitular = turno.titular === null;
  const mio = !sinTitular && turno.titular.id === usuario.id;
  const esMedico = usuario.rol !== "COORDINADOR";
  const horas = horasHasta(turno, ahora);
  const empezado = horas < 0;

  if (mio) {
    const urgente = vacanteAbierta && horas < 24 && !empezado;
    return {
      ...vacio,
      tipo: vacanteAbierta ? "VACANTE" : "NORMAL",
      etiqueta: vacanteAbierta ? (urgente ? "Vacante urgente" : "Vacante") : null,
      urgente,
      acciones: esMedico ? [vacanteAbierta ? "RETIRAR_AVISO" : "AVISAR_AUSENCIA"] : [],
    };
  }

  let acciones = [];
  if (esMedico) {
    if (postulado) acciones = ["RETIRAR_POSTULACION"];
    else if (!empezado) acciones = ["POSTULARME"];
  }
  return { ...vacio, tipo: sinTitular ? "BAJA" : "NORMAL", etiqueta: sinTitular ? "BAJA" : null, postulado: esMedico && postulado, acciones };
}

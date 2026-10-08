import { crearRecuerdo } from "./recuerdo.js";

// Vacantes contra la API real (D15, D32). El servidor no lista las vacantes abiertas de un médico, así que
// las que se generan desde este navegador se recuerdan acá para poder retirarlas (ver el plan de F6).

export const generarVacante = (api, turnoId, motivo) =>
  api.post(`/api/turnos/${turnoId}/vacantes`, { motivo: motivo || null });

// Solo coordinadores: el servidor responde 403 SIN_PERMISO a un médico.
export const generarLote = (api, turnoIds, motivo) =>
  api.post("/api/vacantes/lote", { turnoIds, motivo: motivo || null });

export const retirarVacante = (api, vacanteId) => api.post(`/api/vacantes/${vacanteId}/retiro`);

const recuerdo = crearRecuerdo("vacantes");
export const leerRecordadas = recuerdo.leer;
export const recordar = recuerdo.recordar;
export const olvidar = recuerdo.olvidar;

// Postulaciones propias contra la API real (D16). El servidor solo devuelve el id de la postulación al crearla,
// así que se recuerda en este navegador para poder retirarla (ver el plan de F6 coordinador y PWA).
import { crearRecuerdo } from "./recuerdo.js";

export const postular = (api, turnoId) => api.post(`/api/turnos/${turnoId}/postulaciones`);

export const retirarPostulacion = (api, postulacionId) => api.post(`/api/postulaciones/${postulacionId}/retiro`);

const recuerdo = crearRecuerdo("postulaciones");
export const leerRecordadas = recuerdo.leer;
export const recordar = recuerdo.recordar;
export const olvidar = recuerdo.olvidar;

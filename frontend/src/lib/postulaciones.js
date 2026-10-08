// Postulaciones propias contra la API real (D16). `GET /turnos` informa la postulación activa de quien consulta
// (`miPostulacionId`), así que no se guarda nada en el navegador.
export const postular = (api, turnoId) => api.post(`/api/turnos/${turnoId}/postulaciones`);

export const retirarPostulacion = (api, postulacionId) => api.post(`/api/postulaciones/${postulacionId}/retiro`);

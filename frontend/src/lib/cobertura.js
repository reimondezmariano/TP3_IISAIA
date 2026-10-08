// Cobertura de un turno desde la coordinación (D17 a D19). El orden de los candidatos lo decide el servidor.
export const candidatosDe = (api, turnoId) => api.get(`/api/turnos/${turnoId}/candidatos`);

export const asignar = (api, turnoId, medicoId, reasignar) =>
  api.put(`/api/turnos/${turnoId}/asignacion`, { medicoId, reasignar });

export const marcarSinCobertura = (api, turnoId) => api.post(`/api/turnos/${turnoId}/sin-cobertura`);

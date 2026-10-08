// Vacantes contra la API real (D15, D32). La vacante abierta de cada turno la informa GET /api/turnos.

export const generarVacante = (api, turnoId, motivo) =>
  api.post(`/api/turnos/${turnoId}/vacantes`, { motivo: motivo || null });

// Solo coordinadores: el servidor responde 403 SIN_PERMISO a un médico.
export const generarLote = (api, turnoIds, motivo) =>
  api.post("/api/vacantes/lote", { turnoIds, motivo: motivo || null });

export const retirarVacante = (api, vacanteId) => api.post(`/api/vacantes/${vacanteId}/retiro`);

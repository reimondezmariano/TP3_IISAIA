// Vacantes contra la API real (D15, D32). El servidor no lista las vacantes abiertas de un médico, así que
// las que se generan desde este navegador se recuerdan acá para poder retirarlas (ver el plan de F6).

export const generarVacante = (api, turnoId, motivo) =>
  api.post(`/api/turnos/${turnoId}/vacantes`, { motivo: motivo || null });

// Solo coordinadores: el servidor responde 403 SIN_PERMISO a un médico.
export const generarLote = (api, turnoIds, motivo) =>
  api.post("/api/vacantes/lote", { turnoIds, motivo: motivo || null });

export const retirarVacante = (api, vacanteId) => api.post(`/api/vacantes/${vacanteId}/retiro`);

const clave = (usuarioId) => `guardia-viva:vacantes:${usuarioId}`;

export function leerRecordadas(usuarioId) {
  try {
    const datos = JSON.parse(window.localStorage.getItem(clave(usuarioId)));
    if (!datos || typeof datos !== "object" || Array.isArray(datos)) return {};
    return Object.fromEntries(Object.entries(datos).filter(([, id]) => Number.isInteger(id)));
  } catch {
    return {};
  }
}

function guardar(usuarioId, datos) {
  try {
    window.localStorage.setItem(clave(usuarioId), JSON.stringify(datos));
  } catch {
    // sin almacenamiento la pantalla funciona igual; solo se pierde el botón de retirar al recargar
  }
}

export function recordar(usuarioId, turnoId, vacanteId) {
  guardar(usuarioId, { ...leerRecordadas(usuarioId), [turnoId]: vacanteId });
}

export function olvidar(usuarioId, turnoId) {
  const { [turnoId]: _quitada, ...resto } = leerRecordadas(usuarioId);
  guardar(usuarioId, resto);
}

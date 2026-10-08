// Ids que el servidor entrega al crear algo y no vuelve a informar (vacantes y postulaciones propias), guardados
// en el navegador por usuario: { turnoId: id }. Si el almacenamiento falla, la pantalla funciona igual.
export function crearRecuerdo(prefijo) {
  const clave = (usuarioId) => `guardia-viva:${prefijo}:${usuarioId}`;

  function leer(usuarioId) {
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
      // se pierde solo la posibilidad de retirar después de recargar
    }
  }

  return {
    leer,
    recordar: (usuarioId, turnoId, id) => guardar(usuarioId, { ...leer(usuarioId), [turnoId]: id }),
    olvidar(usuarioId, turnoId) {
      const { [turnoId]: _quitado, ...resto } = leer(usuarioId);
      guardar(usuarioId, resto);
    },
  };
}

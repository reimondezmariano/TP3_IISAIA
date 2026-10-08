// Registra el service worker solo en producción: en desarrollo cachearía archivos que cambian todo el tiempo.
export async function registrarServiceWorker({ navegador = globalThis.navigator, produccion = import.meta.env.PROD } = {}) {
  if (!produccion || !navegador?.serviceWorker) return;
  try {
    await navegador.serviceWorker.register("/sw.js");
  } catch {
    // sin service worker la app funciona igual; solo no queda disponible el shell sin conexión
  }
}

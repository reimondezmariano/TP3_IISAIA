// Service worker básico: guarda el shell de la app para abrirla sin conexión. Nunca toca /api/ (los datos
// siempre vienen del servidor) ni pedidos que no sean GET del mismo origen.
const VERSION = "guardia-viva-v2";
const SHELL = ["/", "/manifest.webmanifest", "/icono-192.png", "/icono-512.png"];

self.addEventListener("install", (evento) => {
  // un recurso que no se pueda traer no impide instalar: el shell se completa con lo que haya
  evento.waitUntil(
    caches
      .open(VERSION)
      .then((cache) => Promise.all(SHELL.map((ruta) => cache.add(ruta).catch(() => {}))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches
      .keys()
      .then((claves) => Promise.all(claves.filter((c) => c !== VERSION).map((c) => caches.delete(c))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (evento) => {
  const pedido = evento.request;
  const url = new URL(pedido.url);
  if (pedido.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  if (pedido.mode === "navigate") {
    // red primero; sin red, el shell guardado
    evento.respondWith(fetch(pedido).catch(() => caches.match("/")));
    return;
  }
  // solo los archivos compilados (/assets/, con hash en el nombre) van con caché primero; el resto va a la red
  if (!url.pathname.startsWith("/assets/")) return;
  evento.respondWith(
    caches.match(pedido).then(
      (guardado) =>
        guardado ||
        fetch(pedido).then((respuesta) => {
          if (respuesta.ok) {
            const copia = respuesta.clone();
            caches.open(VERSION).then((cache) => cache.put(pedido, copia));
          }
          return respuesta;
        }),
    ),
  );
});

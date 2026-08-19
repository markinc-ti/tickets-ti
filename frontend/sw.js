// Service worker mínimo — su única función aquí es hacer que el
// navegador considere la app "instalable" (requisito técnico de PWA).
// No cachea datos de tickets: siempre se piden frescos al servidor,
// para que nadie vea información desactualizada.

const CACHE_NAME = "tickets-ti-shell-v3";
const SHELL_FILES = ["/", "/static/icon-192.png", "/static/icon-512.png", "/static/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Al activarse una versión nueva, borra CUALQUIER caché de una versión
  // anterior — así nunca se queda pegada una copia vieja de la app.
  event.waitUntil(
    caches.keys()
      .then((nombres) => Promise.all(nombres.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

// Solo usa la caché como respaldo si no hay conexión; con red, SIEMPRE va al
// servidor y nunca a la caché HTTP normal del navegador (cache: 'no-store'),
// para que un archivo nuevo se vea de inmediato sin tener que limpiar nada a mano.
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request, { cache: "no-store" }).catch(() => caches.match(event.request))
  );
});

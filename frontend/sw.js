// Service worker mínimo — su única función aquí es hacer que el
// navegador considere la app "instalable" (requisito técnico de PWA).
// No cachea datos de tickets: siempre se piden frescos al servidor,
// para que nadie vea información desactualizada.

const CACHE_NAME = "tickets-ti-shell-v1";
const SHELL_FILES = ["/", "/static/icon-192.png", "/static/icon-512.png", "/static/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// Solo usa la caché como respaldo si no hay conexión; si hay red, siempre prefiere red.
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

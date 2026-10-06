"use strict";

const CACHE_NAME = "acervo-static-v1";
const STATIC_PATHS = [
  "/static/vendor/bootstrap/bootstrap.min.css",
  "/static/vendor/bootstrap/bootstrap.bundle.min.js",
  "/static/vendor/htmx/htmx.min.js",
  "/static/vendor/jsqr/jsQR.js",
  "/static/css/acervo.css",
  "/static/js/pwa-register.js",
  "/static/js/qr-scan.js",
  "/static/pwa/icon-192.png",
  "/static/pwa/icon-512.png",
  "/static/pwa/offline.html",
];
const STATIC_SET = new Set(STATIC_PATHS);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      cache.addAll(STATIC_PATHS.map((path) => new Request(path, { credentials: "omit", cache: "reload" })))
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key.startsWith("acervo-static-") && key !== CACHE_NAME)
        .map((key) => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(async () =>
        (await caches.open(CACHE_NAME)).match("/static/pwa/offline.html")
      )
    );
    return;
  }

  if (STATIC_SET.has(url.pathname) && !url.search) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request))
    );
  }
});

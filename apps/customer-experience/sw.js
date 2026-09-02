const CACHE_NAME = "phil-ai-os-cx-sprint4-v6";
const APP_SHELL = [
  "./",
  "./index.html",
  "./cart-preview.html",
  "./styles.css",
  "./manifest.webmanifest",
  "./app-icon.svg",
  "./src/app.mjs",
  "./src/core.mjs",
  "./src/cart.mjs",
  "./src/cart-preview.mjs",
  "./src/flow.mjs",
  "./src/payment.mjs",
  "./src/pickup.mjs",
  "./src/readiness-feedback.mjs",
  "./src/seo.mjs",
  "./fixtures/catalog.json",
  "./fixtures/payment-provider.json",
  "./fixtures/pickup-policy.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;

  event.respondWith(
    caches.match(event.request).then(async (cached) => {
      if (cached) return cached;
      try {
        const response = await fetch(event.request);
        if (response && response.status === 200 && response.type !== "opaque") {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        }
        return response;
      } catch {
        if (event.request.mode === "navigate") {
          const shell = await caches.match("./index.html");
          if (shell) return shell;
        }
        return new Response("", { status: 503, statusText: "Offline" });
      }
    })
  );
});

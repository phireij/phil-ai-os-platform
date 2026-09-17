const CACHE_NAME = "phil-ai-os-cx-sprint4-v32";
// 2026-09-17: cache the isolated first-party Quick Pickup route foundation and fixture-only controls while preserving network-first branded Ruby preview refresh behavior.
const APP_SHELL = [
  "./",
  "./index.html",
  "./cart-preview.html",
  "./confirmation-preview.html",
  "./quick-pickup-preview.html",
  "./quick-pickup.html",
  "./order-intake-preview.html",
  "./styles.css",
  "./connectivity-status.css",
  "./product-browse-ux.css",
  "./product-detail-facts.css",
  "./mobile-performance.css",
  "./product-media-resilience.css",
  "./mobile-narrow-screen.css",
  "./cart-mobile-controls.css",
  "./fulfillment-choice.css",
  "./checkout-context-summary.css",
  "./payment-method-guidance.css",
  "./final-review-summary.css",
  "./order-intake-preview.css",
  "./manifest.webmanifest",
  "./app-icon.svg",
  "./src/app.mjs",
  "./src/mobile-ux.mjs",
  "./src/product-browse-ux.mjs",
  "./src/product-detail-facts.mjs",
  "./src/locale-links.mjs",
  "./src/connectivity-status.mjs",
  "./src/page-chrome-locale.mjs",
  "./src/core.mjs",
  "./src/cart.mjs",
  "./src/cart-preview.mjs",
  "./src/cart-selection-continuity.mjs",
  "./src/cart-mobile-controls.mjs",
  "./src/cart-locale-state.mjs",
  "./src/empty-cart-recovery.mjs",
  "./src/fulfillment-choice.mjs",
  "./src/cart-form-guard.mjs",
  "./src/cart-dock-status.mjs",
  "./src/cart-session-recovery.mjs",
  "./src/checkout-context-summary.mjs",
  "./src/payment-method-guidance.mjs",
  "./src/checkout-confidence.mjs",
  "./src/confirmation-preview.mjs",
  "./src/final-review-summary.mjs",
  "./src/final-review-navigation.mjs",
  "./src/flow.mjs",
  "./src/payment.mjs",
  "./src/pickup.mjs",
  "./src/quick-pickup-availability.mjs",
  "./src/quick-pickup-capacity.mjs",
  "./src/quick-pickup-decision-preview.mjs",
  "./src/quick-pickup-disable-control.mjs",
  "./src/quick-pickup-preview.mjs",
  "./src/quick-pickup-route.mjs",
  "./src/order-intake-preview.mjs",
  "./src/order-intake-draft-state.mjs",
  "./src/order-intake-review-state.mjs",
  "./src/order-intake-review-summary.mjs",
  "./src/order-intake-review-continuity.mjs",
  "./src/order-intake-cart-context.mjs",
  "./src/order-intake-final-review.mjs",
  "./src/order-intake-request-envelope.mjs",
  "./src/order-intake-review-handoff.mjs",
  "./src/readiness-feedback.mjs",
  "./src/seo.mjs",
  "./src/ui-state.mjs",
  "./fixtures/catalog.json",
  "./fixtures/final-confirmation.json",
  "./fixtures/payment-provider.json",
  "./fixtures/pickup-policy.json",
  "./fixtures/first-party-quick-pickup.json",
  "./fixtures/quick-pickup-inventory-snapshot.json",
  "./fixtures/quick-pickup-capacity-snapshot.json",
  "./fixtures/quick-pickup-disable-control.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))));
  self.clients.claim();
});

async function cacheSuccessful(request, response) {
  if (response && response.status === 200 && response.type !== "opaque") {
    const copy = response.clone();
    await caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
  }
  return response;
}

async function navigationResponse(request) {
  try {
    const response = await fetch(request);
    return cacheSuccessful(request, response);
  } catch {
    const exact = await caches.match(request);
    if (exact) return exact;
    const shell = await caches.match("./index.html");
    if (shell) return shell;
    return new Response("", { status: 503, statusText: "Offline" });
  }
}

async function staticResponse(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    return cacheSuccessful(request, response);
  } catch {
    return new Response("", { status: 503, statusText: "Offline" });
  }
}

function isRubyPreviewAsset(url) {
  return url.pathname.includes("/src/ruby-")
    || url.pathname.endsWith("/ruby-storefront-progress.css")
    || url.pathname.endsWith("/ruby-product-preview.css")
    || url.pathname.endsWith("/ruby-preview-cart.css");
}

async function rubyPreviewStaticResponse(request) {
  try {
    const response = await fetch(request, { cache: "no-store" });
    return cacheSuccessful(request, response);
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response("", { status: 503, statusText: "Offline" });
  }
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (event.request.mode === "navigate") {
    event.respondWith(navigationResponse(event.request));
    return;
  }
  event.respondWith(isRubyPreviewAsset(url) ? rubyPreviewStaticResponse(event.request) : staticResponse(event.request));
});

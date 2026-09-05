import "./page-chrome-locale.mjs";

const COPY = Object.freeze({
  en: Object.freeze({
    online: "Connection available · isolated preview only",
    offline: "Offline · cached preview only. Information may be stale; orders and payments cannot be submitted.",
  }),
  ja: Object.freeze({
    online: "接続あり・隔離プレビューのみ",
    offline: "オフライン・キャッシュ済みプレビューのみ。情報が最新でない可能性があります。注文送信・決済実行はできません。",
  }),
});

export function connectivityLocale(root = document) {
  return root.documentElement?.lang === "ja" ? "ja" : "en";
}

export function connectivityMessage({ online, locale }) {
  const selected = locale === "ja" ? "ja" : "en";
  return online ? COPY[selected].online : COPY[selected].offline;
}

export function renderConnectivityStatus(root = document, online = navigator.onLine) {
  let status = root.querySelector("#connectivity-status");
  if (!status) {
    status = root.createElement("div");
    status.id = "connectivity-status";
    status.className = "connectivity-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.setAttribute("aria-atomic", "true");
    const header = root.querySelector(".site-header");
    if (header?.after) header.after(status);
    else root.body?.prepend(status);
  }
  const locale = connectivityLocale(root);
  status.dataset.connection = online ? "online" : "offline";
  status.textContent = connectivityMessage({ online, locale });
  return status;
}

export function installConnectivityStatus(root = document, target = window) {
  const render = () => renderConnectivityStatus(root, navigator.onLine);
  render();
  target.addEventListener("online", render);
  target.addEventListener("offline", render);
  root.querySelector("#locale-select")?.addEventListener("change", () => queueMicrotask(render));
  return Object.freeze({
    mutation_authorized: false,
    order_creation_authorized: false,
    payment_execution_authorized: false,
  });
}

if (typeof document !== "undefined" && typeof window !== "undefined") {
  installConnectivityStatus();
}

import { firstPartyQuickPickupUiState, validateFirstPartyQuickPickupConfig } from "./pickup.mjs";
import { syncLocaleLinks } from "./locale-links.mjs";

const copy = {
  en: {
    skipToContent: "Skip to content",
    brand: "Customer Experience",
    languageLabel: "Language",
    previewStatus: "Isolated preview · No production activation",
    footer: "Phil AI OS · Sprint 4 Customer Experience · fixture-only Quick Pickup readiness",
    heroTitle: "Ruby first-party Quick Pickup readiness",
    heroCopy: "This preview reads fixture-only readiness state. It does not create orders, reserve inventory, publish a route, or activate payment.",
    title: "Readiness status",
    pending: "Ruby's first-party Quick Pickup route is not implemented yet. No customer order path is available.",
    activationPending: "The Quick Pickup route exists, but required readiness gates are still pending.",
    ready: "Quick Pickup has passed its configured readiness gates for controlled activation.",
    open: "Open Quick Pickup",
    safetyTitle: "No customer route is activated automatically",
    safetyCopy: "Implementation, eligible catalog, inventory freshness, capacity, payment, bilingual copy, operator acceptance, and rollback controls must all be GREEN before an approved route may be exposed. Automatic execution remains disabled.",
    technical: "Technical readiness details",
    shop: "Shop",
    cart: "Cart",
    pickup: "Pickup",
    navLabel: "Mobile Quick Pickup navigation",
  },
  ja: {
    skipToContent: "本文へ移動",
    brand: "カスタマーエクスペリエンス",
    languageLabel: "言語",
    previewStatus: "分離プレビュー · 本番有効化なし",
    footer: "Phil AI OS · Sprint 4 カスタマーエクスペリエンス · フィクスチャ専用クイックピックアップ準備状況",
    heroTitle: "Ruby独自クイックピックアップ準備状況",
    heroCopy: "このプレビューはフィクスチャ専用の準備状況のみを読み取ります。注文作成、在庫確保、ルート公開、決済有効化は行いません。",
    title: "準備状況",
    pending: "Ruby独自のクイックピックアップ受取ルートはまだ実装されていません。現在、注文導線は利用できません。",
    activationPending: "クイックピックアップのルートはありますが、必要な準備ゲートがまだ完了していません。",
    ready: "クイックピックアップは管理された有効化に必要な準備ゲートを通過しています。",
    open: "クイックピックアップを開く",
    safetyTitle: "注文導線は自動で有効化されません",
    safetyCopy: "実装、対象カタログ、在庫鮮度、受取可能数、決済、日英コピー、運用者確認、ロールバック管理がすべてGREENになった場合のみ、承認済みルートを公開できます。自動実行は無効のままです。",
    technical: "技術的な準備状況",
    shop: "商品",
    cart: "カート",
    pickup: "受取",
    navLabel: "モバイル・クイックピックアップ・ナビゲーション",
  },
};

const localeSelect = document.querySelector("#locale-select");
const output = document.querySelector("#quick-pickup-state");
let config;
let locale = new URLSearchParams(location.search).get("lang") === "ja" ? "ja" : "en";

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function syncMobileNavigation() {
  document.querySelector("#dock-shop-label")?.replaceChildren(copy[locale].shop);
  document.querySelector("#dock-cart-label")?.replaceChildren(copy[locale].cart);
  document.querySelector("#dock-pickup-label")?.replaceChildren(copy[locale].pickup);
  document.querySelector(".mobile-action-dock")?.setAttribute("aria-label", copy[locale].navLabel);
  syncLocaleLinks(locale);
}

function syncSharedChrome() {
  const c = copy[locale];
  localeSelect.setAttribute("aria-label", c.languageLabel);
  document.querySelector(".skip-link").textContent = c.skipToContent;
  document.querySelector(".site-header .brand").textContent = c.brand;
  document.querySelector(".locale-label").textContent = c.languageLabel;
  document.querySelector(".hero .status-pill").textContent = c.previewStatus;
  document.querySelector("footer p").textContent = c.footer;
}

function render() {
  document.documentElement.lang = locale;
  localeSelect.value = locale;
  syncSharedChrome();
  document.querySelector("#hero-title").textContent = copy[locale].heroTitle;
  document.querySelector("#hero-copy").textContent = copy[locale].heroCopy;
  document.querySelector("#quick-pickup-title").textContent = copy[locale].title;
  document.querySelector("#safety-title").textContent = copy[locale].safetyTitle;
  document.querySelector("#safety-copy").textContent = copy[locale].safetyCopy;
  syncMobileNavigation();

  const state = firstPartyQuickPickupUiState(config);
  const message = state.reason === "controlled_activation_ready"
    ? copy[locale].ready
    : state.reason === "readiness_pending"
      ? copy[locale].activationPending
      : copy[locale].pending;

  output.innerHTML = `<strong>${escapeHtml(message)}</strong>`;
  if (state.available && state.href) {
    const link = document.createElement("a");
    link.className = "detail-link";
    link.href = state.href;
    link.rel = "noopener noreferrer";
    link.textContent = copy[locale].open;
    output.append(document.createElement("p")).append(link);
  }

  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = copy[locale].technical;
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify({
    available: state.available,
    href_exposed: Boolean(state.href),
    reason: state.reason,
    air_mobile_order_required_for_v1: config.air_mobile_order_required_for_v1,
    route_implemented: config.route_implemented,
    eligible_catalog_confirmed: config.eligible_catalog_confirmed,
    inventory_freshness_control_green: config.inventory_freshness_control_green,
    capacity_and_cutoff_control_green: config.capacity_and_cutoff_control_green,
    checkout_and_payment_contract_green: config.checkout_and_payment_contract_green,
    bilingual_customer_copy_green: config.bilingual_customer_copy_green,
    controlled_handset_and_operator_acceptance_green: config.controlled_handset_and_operator_acceptance_green,
    rollback_disable_path_green: config.rollback_disable_path_green,
    activation_authorized: config.activation_authorized,
    automatic_production_execution_authorized: config.automatic_production_execution_authorized,
  }, null, 2);
  details.append(summary, pre);
  output.append(details);
}

async function boot() {
  const response = await fetch("./fixtures/first-party-quick-pickup.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`quick pickup fixture failed: ${response.status}`);
  config = await response.json();
  validateFirstPartyQuickPickupConfig(config);
  render();

  localeSelect.addEventListener("change", () => {
    locale = localeSelect.value === "ja" ? "ja" : "en";
    const url = new URL(location.href);
    url.searchParams.set("lang", locale);
    history.replaceState(null, "", url);
    render();
  });
}

boot().catch(() => {
  document.documentElement.lang = locale;
  localeSelect.value = locale;
  syncSharedChrome();
  syncMobileNavigation();
  output.textContent = locale === "ja"
    ? "準備状況を読み込めませんでした。注文導線は有効化されていません。"
    : "Readiness state could not be loaded. No customer order path has been activated.";
  output.setAttribute("role", "alert");
});

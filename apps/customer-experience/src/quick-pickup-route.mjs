import { firstPartyQuickPickupUiState, validateFirstPartyQuickPickupConfig } from "./pickup.mjs";
import { applyQuickPickupDisableControl, validateQuickPickupDisableControl } from "./quick-pickup-disable-control.mjs";
import {
  buildDeterministicQuickPickupFixtureRequest,
  evaluateQuickPickupDecisionPreview,
} from "./quick-pickup-decision-preview.mjs";
import { syncLocaleLinks } from "./locale-links.mjs";

const copy = {
  en: {
    language: "Language",
    status: "Isolated route · Ordering disabled",
    hero: "Quick Pickup route foundation",
    heroCopy: "This route is implemented for controlled testing only. It cannot reserve stock, book a pickup slot, create an order, or execute payment.",
    routeTitle: "Customer ordering is not available",
    routePending: "The route exists, but activation and independent readiness gates are still pending.",
    routeDisabled: "The operator disable control is engaged. No customer order path is available.",
    fixtureTitle: "No live inventory or reservation",
    fixtureAvailable: "Historical fixture data passes the synthetic stock and slot demonstration.",
    fixtureBlocked: "Historical fixture data is blocked by the synthetic stock or slot demonstration.",
    fixtureSafety: "Synthetic data only. This result does not hold stock, reserve capacity, create an order, authorize payment, or publish this route.",
    shop: "Shop",
    cart: "Cart",
    pickup: "Pickup status",
    nav: "Quick Pickup route navigation",
    footer: "Pre-production route foundation · No customer order action",
  },
  ja: {
    language: "言語",
    status: "分離ルート · 注文無効",
    hero: "クイックピックアップ・ルート基盤",
    heroCopy: "このルートは管理されたテスト用に実装されています。在庫確保、受取枠予約、注文作成、決済実行はできません。",
    routeTitle: "お客様の注文はまだ利用できません",
    routePending: "ルートは存在しますが、有効化と独立した準備ゲートは未完了です。",
    routeDisabled: "運用者の無効化コントロールが有効です。お客様の注文導線は利用できません。",
    fixtureTitle: "実在庫・予約ではありません",
    fixtureAvailable: "過去のフィクスチャデータは合成在庫・受取枠デモの条件を満たしています。",
    fixtureBlocked: "過去のフィクスチャデータは合成在庫または受取枠デモにより停止されています。",
    fixtureSafety: "合成データのみです。在庫確保、受取枠予約、注文作成、決済承認、ルート公開は行いません。",
    shop: "商品",
    cart: "カート",
    pickup: "受取状況",
    nav: "クイックピックアップ・ルート・ナビゲーション",
    footer: "本番前ルート基盤 · お客様の注文操作なし",
  },
};

let locale = new URLSearchParams(location.search).get("lang") === "ja" ? "ja" : "en";
let config;
let disableControl;
let decision;
let controlledRouteState;
const localeSelect = document.querySelector("#locale-select");
const routeOutput = document.querySelector("#route-output");
const fixtureOutput = document.querySelector("#fixture-output");

function render() {
  const c = copy[locale];
  document.documentElement.lang = locale;
  localeSelect.value = locale;
  localeSelect.setAttribute("aria-label", c.language);
  document.querySelector(".locale-label").textContent = c.language;
  document.querySelector("#route-status").textContent = c.status;
  document.querySelector("#hero-title").textContent = c.hero;
  document.querySelector("#hero-copy").textContent = c.heroCopy;
  document.querySelector("#route-title").textContent = c.routeTitle;
  document.querySelector("#safety-title").textContent = c.fixtureTitle;
  document.querySelector("#dock-shop-label").textContent = c.shop;
  document.querySelector("#dock-cart-label").textContent = c.cart;
  document.querySelector("#dock-pickup-label").textContent = c.pickup;
  document.querySelector(".mobile-action-dock").setAttribute("aria-label", c.nav);
  document.querySelector("#footer-copy").textContent = c.footer;
  syncLocaleLinks(locale);

  routeOutput.replaceChildren();
  const routeMessage = document.createElement("strong");
  routeMessage.textContent = controlledRouteState.reason === "operator_disable_engaged" ? c.routeDisabled : c.routePending;
  routeOutput.append(routeMessage);

  const routeTechnical = document.createElement("pre");
  routeTechnical.textContent = JSON.stringify({
    route_implemented: config.route_implemented,
    customer_route_configured: Boolean(config.customer_route),
    route_available: controlledRouteState.available,
    href_exposed: Boolean(controlledRouteState.href),
    route_reason: controlledRouteState.reason,
    activation_authorized: config.activation_authorized,
    operator_disable_engaged: disableControl.disable_engaged,
    order_creation_authorized: false,
    payment_execution_authorized: false,
    production_publish_authorized: false,
  }, null, 2);
  routeOutput.append(routeTechnical);

  fixtureOutput.replaceChildren();
  const fixtureResult = document.createElement("strong");
  fixtureResult.textContent = decision.available ? c.fixtureAvailable : c.fixtureBlocked;
  const fixtureSafety = document.createElement("p");
  fixtureSafety.textContent = c.fixtureSafety;
  fixtureOutput.append(fixtureResult, fixtureSafety);
}

async function boot() {
  const [configResponse, inventoryResponse, capacityResponse, disableResponse] = await Promise.all([
    fetch("./fixtures/first-party-quick-pickup.json", { cache: "no-store" }),
    fetch("./fixtures/quick-pickup-inventory-snapshot.json", { cache: "no-store" }),
    fetch("./fixtures/quick-pickup-capacity-snapshot.json", { cache: "no-store" }),
    fetch("./fixtures/quick-pickup-disable-control.json", { cache: "no-store" }),
  ]);
  for (const response of [configResponse, inventoryResponse, capacityResponse, disableResponse]) {
    if (!response.ok) throw new Error(`Quick Pickup route fixture failed: ${response.status}`);
  }

  const [inventory, capacity] = await Promise.all([inventoryResponse.json(), capacityResponse.json()]);
  config = await configResponse.json();
  disableControl = await disableResponse.json();
  validateFirstPartyQuickPickupConfig(config);
  validateQuickPickupDisableControl(disableControl);

  const routeState = firstPartyQuickPickupUiState(config);
  controlledRouteState = applyQuickPickupDisableControl(routeState, disableControl);
  const request = buildDeterministicQuickPickupFixtureRequest(inventory, capacity);
  decision = evaluateQuickPickupDecisionPreview(request, inventory, capacity);
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
  routeOutput.textContent = locale === "ja"
    ? "ルート状態を読み込めませんでした。注文は無効のままです。"
    : "Route state could not be loaded. Ordering remains disabled.";
  routeOutput.setAttribute("role", "alert");
});

import { firstPartyQuickPickupUiState, validateFirstPartyQuickPickupConfig } from "./pickup.mjs";
import {
  buildDeterministicQuickPickupFixtureRequest,
  evaluateQuickPickupDecisionPreview,
} from "./quick-pickup-decision-preview.mjs";
import { applyQuickPickupDisableControl, validateQuickPickupDisableControl } from "./quick-pickup-disable-control.mjs";
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
    fixtureTitle: "Fixture-only stock + pickup-slot demonstration",
    fixtureAvailable: "The synthetic snapshot has enough sample stock and slot capacity for this demonstration request.",
    fixtureBlocked: "The synthetic demonstration request is blocked by its fail-closed stock or slot checks.",
    fixtureSafety: "Historical test data only — this is not live inventory, not a reservation, and not an order. No customer action is available from this check.",
    disableTitle: "Fixture operator-disable control",
    disableEngaged: "ENGAGED — route exposure is vetoed even if an upstream synthetic route becomes ready.",
    disableReleased: "Released in fixture only — upstream readiness still controls whether any route can be exposed.",
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
    fixtureTitle: "フィクスチャ専用：在庫・受取枠デモ",
    fixtureAvailable: "このデモ用リクエストでは、合成スナップショット上のサンプル在庫と受取枠に余裕があります。",
    fixtureBlocked: "このデモ用リクエストは、在庫または受取枠のフェイルクローズ確認により停止されています。",
    fixtureSafety: "過去のテストデータのみです。実在庫、予約、注文ではなく、この確認画面からお客様の操作はできません。",
    disableTitle: "フィクスチャ専用：運用者停止コントロール",
    disableEngaged: "有効 — 上流の合成ルートが準備完了になっても、ルート公開を強制的に停止します。",
    disableReleased: "フィクスチャ上のみ解除 — ルート公開可否は引き続き上流の準備状況に従います。",
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
let inventorySnapshot;
let capacitySnapshot;
let disableControl;
let decisionRequest;
let decision;
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

function renderFixtureDecision() {
  const section = document.createElement("section");
  section.setAttribute("aria-label", copy[locale].fixtureTitle);

  const heading = document.createElement("h3");
  heading.textContent = copy[locale].fixtureTitle;
  const result = document.createElement("strong");
  result.textContent = decision.available ? copy[locale].fixtureAvailable : copy[locale].fixtureBlocked;
  const safety = document.createElement("p");
  safety.textContent = copy[locale].fixtureSafety;

  section.append(heading, result, safety);
  output.append(section);
}

function renderDisableControl() {
  const section = document.createElement("section");
  section.setAttribute("aria-label", copy[locale].disableTitle);
  const heading = document.createElement("h3");
  heading.textContent = copy[locale].disableTitle;
  const status = document.createElement("strong");
  status.textContent = disableControl.disable_engaged ? copy[locale].disableEngaged : copy[locale].disableReleased;
  section.append(heading, status);
  output.append(section);
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

  const upstreamState = firstPartyQuickPickupUiState(config);
  const state = applyQuickPickupDisableControl(upstreamState, disableControl);
  const message = upstreamState.reason === "controlled_activation_ready"
    ? copy[locale].ready
    : upstreamState.reason === "readiness_pending"
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

  renderDisableControl();
  renderFixtureDecision();

  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = copy[locale].technical;
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify({
    upstream_route: {
      available: upstreamState.available,
      href_exposed: Boolean(upstreamState.href),
      reason: upstreamState.reason,
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
    },
    guarded_route: state,
    disable_control: disableControl,
    fixture_decision: decision,
    fixture_request: decisionRequest,
    fixture_sources: {
      inventory_snapshot_id: inventorySnapshot.snapshot_id,
      capacity_snapshot_id: capacitySnapshot.snapshot_id,
      live_inventory_claimed: false,
      live_capacity_claimed: false,
    },
  }, null, 2);
  details.append(summary, pre);
  output.append(details);
}

async function boot() {
  const [configResponse, inventoryResponse, capacityResponse, disableResponse] = await Promise.all([
    fetch("./fixtures/first-party-quick-pickup.json", { cache: "no-store" }),
    fetch("./fixtures/quick-pickup-inventory-snapshot.json", { cache: "no-store" }),
    fetch("./fixtures/quick-pickup-capacity-snapshot.json", { cache: "no-store" }),
    fetch("./fixtures/quick-pickup-disable-control.json", { cache: "no-store" }),
  ]);
  if (!configResponse.ok) throw new Error(`quick pickup readiness fixture failed: ${configResponse.status}`);
  if (!inventoryResponse.ok) throw new Error(`quick pickup inventory fixture failed: ${inventoryResponse.status}`);
  if (!capacityResponse.ok) throw new Error(`quick pickup capacity fixture failed: ${capacityResponse.status}`);
  if (!disableResponse.ok) throw new Error(`quick pickup disable fixture failed: ${disableResponse.status}`);

  [config, inventorySnapshot, capacitySnapshot, disableControl] = await Promise.all([
    configResponse.json(),
    inventoryResponse.json(),
    capacityResponse.json(),
    disableResponse.json(),
  ]);
  validateFirstPartyQuickPickupConfig(config);
  validateQuickPickupDisableControl(disableControl);
  decisionRequest = buildDeterministicQuickPickupFixtureRequest(inventorySnapshot, capacitySnapshot);
  decision = evaluateQuickPickupDecisionPreview(decisionRequest, inventorySnapshot, capacitySnapshot);
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

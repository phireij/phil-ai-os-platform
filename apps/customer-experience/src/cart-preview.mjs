import { buildCartCheckoutIntent, cartPricingSummary } from "./cart.mjs";
import { evaluateCheckoutReadiness, formatMoney, localized, normalizeLocale } from "./core.mjs";
import { buildPaymentHandoffIntent, validatePaymentProviderProfile } from "./payment.mjs";
import { evaluatePickupSelection, validatePickupPolicy } from "./pickup.mjs";
import { readinessFeedback } from "./readiness-feedback.mjs";

const copy = {
  en: {
    skipToContent: "Skip to content",
    brand: "Customer Experience",
    languageLabel: "Language",
    previewStatus: "Isolated preview · KOMOJU not connected",
    footer: "Phil AI OS · Sprint 4 · synthetic cart/payment-handoff environment",
    heroTitle: "Multi-item checkout and payment handoff",
    heroCopy: "Synthetic data only. This page prepares a non-authorizing KOMOJU handoff intent after local checkout readiness succeeds.",
    cartTitle: "Synthetic cart",
    pickup: "Preferred pickup time",
    evaluate: "Evaluate checkout & KOMOJU handoff",
    unavailable: "Unavailable",
    quantity: "Quantity",
    resultIdle: "No handoff prepared yet",
    resultIdleCopy: "Choose quantities and a pickup time. This preview never creates an order or executes a payment.",
    resultReady: "KOMOJU handoff intent prepared",
    resultBlocked: "Checkout is not ready",
    resultReadyCopy: "Readiness is GREEN. A non-executable KOMOJU handoff intent was composed; no order or payment was created.",
    resultBlockedCopy: "The handoff remains blocked until all local readiness checks pass.",
    nextSteps: "What to do next",
    technicalDetails: "Technical preview details",
    safetyTitle: "KOMOJU is configured as intent only",
    safetyCopy: "Provider: KOMOJU · integration: WooCommerce plugin · connection: not configured · order creation: false · payment execution: false · live mode: false.",
    selected: (count, total) => `${count} selected item types · ${total}`,
    noItems: "Your cart is empty. Choose a product to continue.",
    error: "Cart preview unavailable",
  },
  ja: {
    skipToContent: "本文へ移動",
    brand: "カスタマーエクスペリエンス",
    languageLabel: "言語",
    previewStatus: "分離プレビュー · KOMOJU未接続",
    footer: "Phil AI OS · Sprint 4 · 合成カート・決済引継ぎ環境",
    heroTitle: "複数商品チェックアウトと決済引継ぎ",
    heroCopy: "合成データのみを使用します。ローカルのチェックアウト準備が成功した場合のみ、実行権限を持たないKOMOJU引継ぎインテントを作成します。",
    cartTitle: "合成カート",
    pickup: "希望受取時間",
    evaluate: "チェックアウトとKOMOJU引継ぎを確認",
    unavailable: "利用不可",
    quantity: "数量",
    resultIdle: "引継ぎはまだ作成されていません",
    resultIdleCopy: "数量と受取時間を選択してください。このプレビューは注文作成や決済実行を行いません。",
    resultReady: "KOMOJU引継ぎインテントを作成しました",
    resultBlocked: "チェックアウトの準備ができていません",
    resultReadyCopy: "準備状況はGREENです。実行不能なKOMOJU引継ぎインテントのみを構成し、注文や決済は作成していません。",
    resultBlockedCopy: "すべてのローカル準備確認が通るまで引継ぎはブロックされます。",
    nextSteps: "次に必要なこと",
    technicalDetails: "技術プレビューの詳細",
    safetyTitle: "KOMOJUはインテントのみとして設定されています",
    safetyCopy: "プロバイダー: KOMOJU · 連携: WooCommerceプラグイン · 接続: 未設定 · 注文作成: false · 決済実行: false · ライブモード: false。",
    selected: (count, total) => `選択商品 ${count} 種類 · ${total}`,
    noItems: "カートは空です。商品を選択して続行してください。",
    error: "カートプレビューを利用できません",
  },
};

const state = {
  locale: normalizeLocale(new URLSearchParams(location.search).get("lang"), navigator.language?.startsWith("ja") ? "ja" : "en"),
  catalog: [],
  pickupPolicy: null,
  paymentProvider: null,
};

const localeSelect = document.querySelector("#locale-select");
const cartItems = document.querySelector("#cart-items");
const cartSummary = document.querySelector("#cart-summary");
const cartForm = document.querySelector("#cart-form");
const pickupAt = document.querySelector("#pickup-at");
const resultTitle = document.querySelector("#result-title");
const result = document.querySelector("#result");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function feedbackList(items) {
  if (!items.length) return "";
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function setCopy() {
  const c = copy[state.locale];
  document.documentElement.lang = state.locale;
  localeSelect.value = state.locale;
  localeSelect.setAttribute("aria-label", c.languageLabel);
  document.querySelector(".skip-link").textContent = c.skipToContent;
  document.querySelector(".site-header .brand").textContent = c.brand;
  document.querySelector(".locale-label").textContent = c.languageLabel;
  document.querySelector(".hero .status-pill").textContent = c.previewStatus;
  document.querySelector("footer p").textContent = c.footer;
  document.querySelector("#hero-title").textContent = c.heroTitle;
  document.querySelector("#hero-copy").textContent = c.heroCopy;
  document.querySelector("#cart-title").textContent = c.cartTitle;
  document.querySelector("#pickup-label").textContent = c.pickup;
  document.querySelector("#evaluate-button").textContent = c.evaluate;
  document.querySelector("#safety-title").textContent = c.safetyTitle;
  document.querySelector("#safety-copy").textContent = c.safetyCopy;
}

function updateLocaleUrl() {
  const url = new URL(location.href);
  url.searchParams.set("lang", state.locale);
  history.replaceState(null, "", url);
}

function defaultQuantity() {
  return 0;
}

function selectedItems() {
  return state.catalog.flatMap((product) => {
    const input = document.querySelector(`[data-cart-sku="${CSS.escape(product.sku)}"]`);
    const quantity = Number(input?.value || 0);
    if (!Number.isInteger(quantity) || quantity < 0) throw new TypeError("quantity must be a non-negative integer");
    return quantity > 0 ? [{ sku: product.sku, quantity }] : [];
  });
}

function renderCart() {
  setCopy();
  cartItems.replaceChildren();
  state.catalog.forEach((product) => {
    const disabled = product.availability !== "in_stock";
    const article = document.createElement("article");
    article.className = "product-card";
    const name = localized(product.name, state.locale);
    const status = disabled ? copy[state.locale].unavailable : product.availability === "in_stock" ? (state.locale === "ja" ? "在庫あり" : "In stock") : product.availability;
    article.innerHTML = `
      <div class="product-card-body">
        <p class="availability ${escapeHtml(product.availability)}">${escapeHtml(status)}</p>
        <h3>${escapeHtml(name)}</h3>
        <p class="description">${escapeHtml(localized(product.short_description, state.locale))}</p>
        <p class="price">${escapeHtml(formatMoney(product.price.amount, product.price.currency, state.locale))}</p>
        <div class="form-field">
          <label for="cart-${escapeHtml(product.sku)}">${escapeHtml(copy[state.locale].quantity)}</label>
          <input id="cart-${escapeHtml(product.sku)}" data-cart-sku="${escapeHtml(product.sku)}" type="number" inputmode="numeric" min="0" step="1" value="${defaultQuantity()}" ${disabled ? "disabled" : ""}>
        </div>
      </div>`;
    cartItems.append(article);
  });
  updateSummary();
}

function updateSummary() {
  try {
    const items = selectedItems();
    if (!items.length) {
      cartSummary.textContent = copy[state.locale].noItems;
      return;
    }
    const pricing = cartPricingSummary(
      { items, mutation_authorized: false },
      new Map(state.catalog.map((product) => [product.sku, product])),
    );
    cartSummary.textContent = copy[state.locale].selected(items.length, formatMoney(pricing.total_amount, pricing.currency, state.locale));
  } catch (error) {
    cartSummary.textContent = error.message;
  }
}

function toIso(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function renderResult({ readiness, pickupReadiness, pricing, handoff = null }) {
  const ready = readiness.ready && Boolean(handoff);
  const feedback = readinessFeedback(readiness, state.locale);
  resultTitle.textContent = ready ? copy[state.locale].resultReady : copy[state.locale].resultBlocked;
  const nextSteps = ready
    ? `<p>${escapeHtml(feedback.summary)}</p>`
    : `<p>${escapeHtml(feedback.summary)}</p><h3>${escapeHtml(copy[state.locale].nextSteps)}</h3>${feedbackList(feedback.action_messages.length ? feedback.action_messages : feedback.blocker_messages)}`;
  result.innerHTML = `
    <p>${escapeHtml(ready ? copy[state.locale].resultReadyCopy : copy[state.locale].resultBlockedCopy)}</p>
    ${nextSteps}
    <details>
      <summary>${escapeHtml(copy[state.locale].technicalDetails)}</summary>
      <pre></pre>
    </details>`;
  result.querySelector("pre").textContent = JSON.stringify({
    pricing,
    pickup_readiness: pickupReadiness,
    checkout_readiness: readiness,
    payment_handoff: handoff,
    customer_feedback: feedback,
  }, null, 2);
}

cartForm.addEventListener("input", updateSummary);
cartForm.addEventListener("submit", (event) => {
  event.preventDefault();
  try {
    const items = selectedItems();
    if (!items.length) throw new Error(copy[state.locale].noItems);
    const requestedPickupAt = toIso(pickupAt.value);
    const intent = buildCartCheckoutIntent({
      intentId: "cx-cart-preview-001",
      locale: state.locale,
      items,
      requestedPickupAt,
    });
    const evaluatedAt = new Date().toISOString();
    const catalogBySku = new Map(state.catalog.map((product) => [product.sku, product]));
    const pricing = cartPricingSummary(intent, catalogBySku);
    const pickupReadiness = evaluatePickupSelection(requestedPickupAt, evaluatedAt, state.pickupPolicy);
    const baseReadiness = evaluateCheckoutReadiness(intent, catalogBySku, evaluatedAt);
    const blockers = new Set(baseReadiness.blockers);
    if (!pickupReadiness.valid) blockers.add("pickup_time");
    const readiness = Object.freeze({
      ...baseReadiness,
      ready: baseReadiness.ready && pickupReadiness.valid,
      blockers: [...blockers].sort(),
      customer_action_required: blockers.has("pickup_time") ? ["select_pickup_time"] : baseReadiness.customer_action_required,
      mutation_authorized: false,
    });
    const handoff = readiness.ready
      ? buildPaymentHandoffIntent({ checkoutIntent: intent, readiness, catalogBySku, providerProfile: state.paymentProvider })
      : null;
    renderResult({ readiness, pickupReadiness, pricing, handoff });
  } catch (error) {
    resultTitle.textContent = copy[state.locale].resultBlocked;
    result.innerHTML = `<p role="alert">${escapeHtml(error.message)}</p>`;
  }
});

localeSelect.addEventListener("change", () => {
  state.locale = normalizeLocale(localeSelect.value);
  updateLocaleUrl();
  renderCart();
  resultTitle.textContent = copy[state.locale].resultIdle;
  result.innerHTML = `<p>${escapeHtml(copy[state.locale].resultIdleCopy)}</p>`;
});

async function fetchFixture(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`fixture failed: ${response.status}`);
  const payload = await response.json();
  if (payload.fixture_only !== true) throw new Error("Sprint 4 cart preview requires fixture_only data");
  return payload;
}

async function boot() {
  const [catalog, pickupPolicy, paymentProvider] = await Promise.all([
    fetchFixture("./fixtures/catalog.json"),
    fetchFixture("./fixtures/pickup-policy.json"),
    fetchFixture("./fixtures/payment-provider.json"),
  ]);
  validatePickupPolicy(pickupPolicy);
  validatePaymentProviderProfile(paymentProvider);
  state.catalog = catalog.products;
  state.pickupPolicy = pickupPolicy;
  state.paymentProvider = paymentProvider;
  renderCart();
  resultTitle.textContent = copy[state.locale].resultIdle;
  result.innerHTML = `<p>${escapeHtml(copy[state.locale].resultIdleCopy)}</p>`;
}

boot().catch((error) => {
  setCopy();
  resultTitle.textContent = copy[state.locale].error;
  result.innerHTML = `<p role="alert">${escapeHtml(error.message)}</p>`;
});

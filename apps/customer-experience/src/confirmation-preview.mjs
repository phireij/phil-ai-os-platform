const APPROVED_PAYMENT_METHODS = Object.freeze(new Set(["credit_card", "konbini", "merpay", "paidy"]));
const AUTHORITY_FLAGS = Object.freeze([
  "order_creation_authorized",
  "mutation_authorized",
  "payment_execution_authorized",
  "production_publish_authorized",
]);

export function normalizeConfirmationLocale(value, fallback = "en") {
  return value === "ja" || value === "en" ? value : fallback;
}

export function confirmationLocalized(value, locale) {
  const selected = normalizeConfirmationLocale(locale);
  if (!value || typeof value !== "object" || typeof value[selected] !== "string" || value[selected].trim() === "") {
    throw new TypeError(`missing required ${selected} confirmation translation`);
  }
  return value[selected];
}

function requireInteger(value, label, minimum = 0) {
  if (!Number.isInteger(value) || value < minimum) {
    throw new TypeError(`${label} must be an integer >= ${minimum}`);
  }
  return value;
}

export function validateFinalConfirmationFixture(payload) {
  if (!payload || typeof payload !== "object") throw new TypeError("final confirmation fixture is required");
  if (payload.fixture_only !== true || payload.preview_only !== true) {
    throw new Error("final confirmation preview requires fixture_only preview_only data");
  }
  if (payload.actual_final_confirmation_screen_reviewed !== false) {
    throw new Error("isolated preview cannot claim actual final-screen acceptance");
  }
  for (const key of AUTHORITY_FLAGS) {
    if (payload[key] !== false) throw new Error(`${key} must remain false`);
  }

  if (!Array.isArray(payload.items) || payload.items.length < 1) throw new Error("confirmation fixture requires at least one item");
  let calculatedSubtotal = 0;
  const seenSkus = new Set();
  for (const item of payload.items) {
    if (typeof item?.sku !== "string" || item.sku.trim() === "" || seenSkus.has(item.sku)) {
      throw new Error("confirmation fixture SKUs must be present and unique");
    }
    seenSkus.add(item.sku);
    confirmationLocalized(item.name, "en");
    confirmationLocalized(item.name, "ja");
    confirmationLocalized(item.option, "en");
    confirmationLocalized(item.option, "ja");
    requireInteger(item.quantity, `${item.sku}.quantity`, 1);
    requireInteger(item.unit_price_jpy, `${item.sku}.unit_price_jpy`, 0);
    calculatedSubtotal += item.quantity * item.unit_price_jpy;
  }

  const pricing = payload.pricing || {};
  requireInteger(pricing.subtotal_jpy, "pricing.subtotal_jpy", 0);
  requireInteger(pricing.shipping_jpy, "pricing.shipping_jpy", 0);
  requireInteger(pricing.total_jpy, "pricing.total_jpy", 0);
  requireInteger(pricing.separate_consumption_tax_jpy, "pricing.separate_consumption_tax_jpy", 0);
  if (pricing.subtotal_jpy !== calculatedSubtotal) throw new Error("confirmation subtotal does not match line items");
  if (pricing.total_jpy !== pricing.subtotal_jpy + pricing.shipping_jpy) throw new Error("confirmation total does not match subtotal plus shipping");
  if (pricing.consumption_tax_status !== "exempt") throw new Error("confirmation tax posture must remain exempt");
  if (pricing.qualified_invoice_status !== "not_registered") throw new Error("confirmation Qualified Invoice posture drift");
  if (pricing.woocommerce_tax_enabled !== false || pricing.separate_consumption_tax_jpy !== 0) {
    throw new Error("isolated confirmation must not add WooCommerce consumption tax under the current posture");
  }

  const shipping = payload.shipping || {};
  if (shipping.method !== "yamato_cool") throw new Error("confirmation shipping method drift");
  requireInteger(shipping.rate_jpy, "shipping.rate_jpy", 0);
  if (shipping.rate_jpy !== pricing.shipping_jpy) throw new Error("shipping rate must equal pricing shipping amount");
  if (shipping.region === "kanto" && shipping.rate_jpy !== 1350) throw new Error("Kanto Yamato Cool rate must remain 1350 JPY");
  confirmationLocalized(shipping.label, "en");
  confirmationLocalized(shipping.label, "ja");

  const payment = payload.payment || {};
  if (!APPROVED_PAYMENT_METHODS.has(payment.method)) throw new Error("payment method is outside the approved initial subset");
  if (payment.provider !== "komoju") throw new Error("confirmation payment provider must remain KOMOJU");
  confirmationLocalized(payment.label, "en");
  confirmationLocalized(payment.label, "ja");
  if (payment.method === "konbini") {
    if (payment.live_expiry_setting_verified !== true || payment.expiry_days !== 3) {
      throw new Error("Konbini confirmation must preserve the verified 3-day Live expiry");
    }
    if (payment.exact_transaction_deadline_controls !== true || payment.example_deadline_only !== true) {
      throw new Error("Konbini preview must defer to the transaction-specific deadline");
    }
    confirmationLocalized(payment.example_deadline, "en");
    confirmationLocalized(payment.example_deadline, "ja");
  }

  const fulfillment = payload.fulfillment || {};
  if (!Array.isArray(fulfillment.dispatch_window_days) || fulfillment.dispatch_window_days.length !== 2 || fulfillment.dispatch_window_days[0] !== 2 || fulfillment.dispatch_window_days[1] !== 5) {
    throw new Error("delivery dispatch window must remain 2–5 days in this fixture");
  }
  if (fulfillment.starts_after_required_payment_completion !== true) throw new Error("fulfillment timing must respect required payment completion");
  confirmationLocalized(fulfillment.summary, "en");
  confirmationLocalized(fulfillment.summary, "ja");

  const cancellation = payload.cancellation || {};
  if (cancellation.full_refund_before_hours !== 48 || cancellation.half_fee_from_hours !== 24 || cancellation.half_fee_to_hours !== 48 || cancellation.full_fee_under_hours !== 24) {
    throw new Error("cancellation timing policy drift");
  }
  confirmationLocalized(cancellation.summary, "en");
  confirmationLocalized(cancellation.summary, "ja");
  confirmationLocalized(payload.returns?.summary, "en");
  confirmationLocalized(payload.returns?.summary, "ja");

  return Object.freeze({
    valid: true,
    fixture_only: true,
    actual_final_confirmation_screen_reviewed: false,
    order_creation_authorized: false,
    mutation_authorized: false,
    payment_execution_authorized: false,
    production_publish_authorized: false,
    subtotal_jpy: pricing.subtotal_jpy,
    shipping_jpy: pricing.shipping_jpy,
    total_jpy: pricing.total_jpy,
    payment_method: payment.method,
  });
}

function formatJpy(value, locale) {
  return new Intl.NumberFormat(locale === "ja" ? "ja-JP" : "en-US", {
    style: "currency",
    currency: "JPY",
    maximumFractionDigits: 0,
  }).format(value);
}

export function buildFinalConfirmationViewModel(payload, locale = "en") {
  const validation = validateFinalConfirmationFixture(payload);
  const selected = normalizeConfirmationLocale(locale);
  return Object.freeze({
    locale: selected,
    items: payload.items.map((item) => Object.freeze({
      sku: item.sku,
      name: confirmationLocalized(item.name, selected),
      option: confirmationLocalized(item.option, selected),
      quantity: item.quantity,
      unitPrice: formatJpy(item.unit_price_jpy, selected),
      lineTotal: formatJpy(item.unit_price_jpy * item.quantity, selected),
    })),
    subtotal: formatJpy(validation.subtotal_jpy, selected),
    shipping: formatJpy(validation.shipping_jpy, selected),
    total: formatJpy(validation.total_jpy, selected),
    shippingLabel: confirmationLocalized(payload.shipping.label, selected),
    paymentLabel: confirmationLocalized(payload.payment.label, selected),
    paymentDeadline: payload.payment.method === "konbini" ? confirmationLocalized(payload.payment.example_deadline, selected) : "",
    fulfillmentSummary: confirmationLocalized(payload.fulfillment.summary, selected),
    cancellationSummary: confirmationLocalized(payload.cancellation.summary, selected),
    returnsSummary: confirmationLocalized(payload.returns.summary, selected),
    taxSummary: selected === "ja"
      ? "2026年の確認済み状態：消費税免税事業者・適格請求書発行事業者未登録・WooCommerce消費税計算無効・別途消費税加算なし。"
      : "Verified 2026 state: consumption-tax exempt, not a Qualified Invoice issuer, WooCommerce tax disabled, no separate consumption-tax amount added.",
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

const copy = Object.freeze({
  en: Object.freeze({
    title: "Final order confirmation — isolated preview",
    intro: "Synthetic fixture only. Review transaction terms together before the final action. This screen never submits an order or executes payment.",
    items: "Order contents",
    pricing: "Price and fees",
    subtotal: "Subtotal",
    shipping: "Shipping",
    total: "Total payable",
    tax: "Tax treatment",
    payment: "Payment",
    fulfillment: "Fulfillment",
    cancellation: "Cancellation / changes",
    returns: "Returns / defects",
    correction: "Need to change something? Return to the synthetic cart before final submission.",
    button: "Place order (preview only — disabled)",
    safety: "Authority boundary: actual WooCommerce final screen reviewed = false · order creation = false · payment execution = false · production publishing = false.",
    error: "Final confirmation preview unavailable",
  }),
  ja: Object.freeze({
    title: "注文の最終確認 — 隔離プレビュー",
    intro: "合成フィクスチャのみを使用します。最終操作の前に取引条件をまとめて確認します。この画面は注文送信や決済実行を行いません。",
    items: "注文内容",
    pricing: "価格・料金",
    subtotal: "小計",
    shipping: "送料",
    total: "お支払い合計",
    tax: "消費税の取扱い",
    payment: "お支払い",
    fulfillment: "引渡し・配送",
    cancellation: "キャンセル・変更",
    returns: "返品・不良品",
    correction: "変更が必要ですか？ 最終送信前に合成カートへ戻って修正してください。",
    button: "注文を確定する（プレビューのみ・無効）",
    safety: "権限境界：実際のWooCommerce最終画面レビュー = false・注文作成 = false・決済実行 = false・本番公開 = false。",
    error: "最終確認プレビューを利用できません",
  }),
});

async function fetchConfirmationFixture() {
  const response = await fetch("./fixtures/final-confirmation.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`fixture failed: ${response.status}`);
  const payload = await response.json();
  if (payload.fixture_only !== true) throw new Error("Sprint 4 final confirmation preview requires fixture_only data");
  return payload;
}

function renderFinalConfirmation(payload, locale) {
  const vm = buildFinalConfirmationViewModel(payload, locale);
  const c = copy[vm.locale];
  document.documentElement.lang = vm.locale;
  document.querySelector("#locale-select").value = vm.locale;
  document.querySelector("#hero-title").textContent = c.title;
  document.querySelector("#hero-copy").textContent = c.intro;
  document.querySelector("#confirmation-title").textContent = c.items;
  document.querySelector("#pricing-title").textContent = c.pricing;
  document.querySelector("#payment-title").textContent = c.payment;
  document.querySelector("#fulfillment-title").textContent = c.fulfillment;
  document.querySelector("#policy-title").textContent = `${c.cancellation} · ${c.returns}`;
  document.querySelector("#correction-copy").textContent = c.correction;
  document.querySelector("#place-order-preview").textContent = c.button;
  document.querySelector("#safety-copy").textContent = c.safety;

  document.querySelector("#confirmation-items").innerHTML = vm.items.map((item) => `
    <article class="product-card">
      <div class="product-card-body">
        <p class="availability">${escapeHtml(item.sku)}</p>
        <h3>${escapeHtml(item.name)}</h3>
        <p>${escapeHtml(item.option)}</p>
        <p>${escapeHtml(vm.locale === "ja" ? `数量 ${item.quantity}` : `Quantity ${item.quantity}`)} · ${escapeHtml(item.unitPrice)} · ${escapeHtml(item.lineTotal)}</p>
      </div>
    </article>`).join("");

  document.querySelector("#pricing-summary").innerHTML = `
    <p>${escapeHtml(c.subtotal)}: <strong>${escapeHtml(vm.subtotal)}</strong></p>
    <p>${escapeHtml(c.shipping)}: <strong>${escapeHtml(vm.shipping)}</strong> · ${escapeHtml(vm.shippingLabel)}</p>
    <p>${escapeHtml(c.total)}: <strong>${escapeHtml(vm.total)}</strong></p>
    <p><strong>${escapeHtml(c.tax)}:</strong> ${escapeHtml(vm.taxSummary)}</p>`;

  document.querySelector("#payment-summary").innerHTML = `
    <p><strong>${escapeHtml(vm.paymentLabel)}</strong></p>
    ${vm.paymentDeadline ? `<p>${escapeHtml(vm.paymentDeadline)}</p>` : ""}`;
  document.querySelector("#fulfillment-summary").textContent = vm.fulfillmentSummary;
  document.querySelector("#policy-summary").innerHTML = `
    <p><strong>${escapeHtml(c.cancellation)}:</strong> ${escapeHtml(vm.cancellationSummary)}</p>
    <p><strong>${escapeHtml(c.returns)}:</strong> ${escapeHtml(vm.returnsSummary)}</p>`;
}

async function boot() {
  const params = new URLSearchParams(location.search);
  let locale = normalizeConfirmationLocale(params.get("lang"), navigator.language?.startsWith("ja") ? "ja" : "en");
  const payload = await fetchConfirmationFixture();
  renderFinalConfirmation(payload, locale);
  document.querySelector("#locale-select").addEventListener("change", (event) => {
    locale = normalizeConfirmationLocale(event.target.value);
    const url = new URL(location.href);
    url.searchParams.set("lang", locale);
    history.replaceState(null, "", url);
    renderFinalConfirmation(payload, locale);
  });
}

if (typeof document !== "undefined") {
  boot().catch((error) => {
    const fallback = navigator.language?.startsWith("ja") ? "ja" : "en";
    document.querySelector("#hero-title").textContent = copy[fallback].error;
    document.querySelector("#hero-copy").textContent = error.message;
  });
}

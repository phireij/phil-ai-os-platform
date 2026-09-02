import {
  buildCheckoutIntent,
  catalogCardViewModel,
  evaluateCheckoutReadiness,
  normalizeLocale,
  productDetailViewModel,
} from "./core.mjs";
import { createCustomerFlow, transitionCustomerFlow } from "./flow.mjs";
import { evaluatePickupSelection } from "./pickup.mjs";
import { readinessFeedback } from "./readiness-feedback.mjs";
import { catalogMetadata, productMetadata } from "./seo.mjs";
import { uiState } from "./ui-state.mjs";

const copy = {
  en: {
    heroTitle: "Mobile-first bilingual storefront foundation",
    heroCopy: "Synthetic data only. This preview proves customer flow without production WooCommerce connectivity.",
    catalogTitle: "Products",
    catalogCount: (count) => `${count} synthetic items`,
    view: "View",
    in_stock: "In stock",
    out_of_stock: "Out of stock",
    backorder: "Backorder",
    unknown: "Availability unknown",
    back: "← Back to catalog",
    pickup: "Pickup",
    quantity: "Quantity",
    pickupTime: "Preferred pickup time",
    evaluate: "Preview checkout readiness",
    intentTitle: "Local checkout intent preview",
    ready: "Ready for a later governed execution step",
    blocked: "Not ready — customer action or inventory review required",
    nextSteps: "What to do next",
    technicalDetails: "Technical preview details",
    noOrder: "No order was created. mutation_authorized remains false.",
    safetyTitle: "Checkout remains an intent",
    safetyCopy: "This Sprint 4 preview can compose and evaluate checkout intent locally. It cannot create an order, charge a payment, or mutate WooCommerce.",
  },
  ja: {
    heroTitle: "モバイルファーストのバイリンガルストア基盤",
    heroCopy: "合成データのみを使用しています。本プレビューは本番WooCommerceへ接続せずに顧客フローを検証します。",
    catalogTitle: "商品",
    catalogCount: (count) => `合成商品 ${count} 件`,
    view: "見る",
    in_stock: "在庫あり",
    out_of_stock: "在庫切れ",
    backorder: "入荷待ち",
    unknown: "在庫状況不明",
    back: "← 商品一覧に戻る",
    pickup: "受取",
    quantity: "数量",
    pickupTime: "希望受取時間",
    evaluate: "チェックアウト準備状況を確認",
    intentTitle: "ローカル・チェックアウトインテント",
    ready: "後続のガバナンス済み実行ステップへ進める状態です",
    blocked: "未準備 — お客様の操作または在庫確認が必要です",
    nextSteps: "次に必要なこと",
    technicalDetails: "技術プレビューの詳細",
    noOrder: "注文は作成されていません。mutation_authorized は false のままです。",
    safetyTitle: "チェックアウトはインテントのままです",
    safetyCopy: "Sprint 4プレビューはチェックアウトインテントの作成と準備評価のみをローカルで行います。注文作成、決済、WooCommerce変更はできません。",
  },
};

const state = {
  locale: normalizeLocale(new URLSearchParams(location.search).get("lang"), navigator.language?.startsWith("ja") ? "ja" : "en"),
  catalog: [],
  pickupPolicy: null,
  flow: createCustomerFlow(),
};

const localeSelect = document.querySelector("#locale-select");
const catalogGrid = document.querySelector("#catalog-grid");
const catalogSummary = document.querySelector("#catalog-summary");
const productSection = document.querySelector("#product-section");
const catalogSection = document.querySelector("#catalog-section");
const productDetail = document.querySelector("#product-detail");
const cardTemplate = document.querySelector("#product-card-template");

function setDocumentLocale() {
  document.documentElement.lang = state.locale;
  localeSelect.value = state.locale;
  document.querySelector("#hero-title").textContent = copy[state.locale].heroTitle;
  document.querySelector("#hero-copy").textContent = copy[state.locale].heroCopy;
  document.querySelector("#catalog-title").textContent = copy[state.locale].catalogTitle;
  document.querySelector("#back-link").textContent = copy[state.locale].back;
  document.querySelector("#safety-title").textContent = copy[state.locale].safetyTitle;
  document.querySelector("#safety-copy").textContent = copy[state.locale].safetyCopy;
}

function applyMetadata(metadata) {
  document.title = metadata.title;
  const description = document.querySelector('meta[name="description"]');
  const robots = document.querySelector('meta[name="robots"]');
  description.setAttribute("content", metadata.description);
  robots.setAttribute("content", metadata.robots);

  document.querySelector('link[rel="canonical"]')?.remove();
  if (metadata.canonical) {
    const canonical = document.createElement("link");
    canonical.rel = "canonical";
    canonical.href = metadata.canonical;
    document.head.append(canonical);
  }

  document.querySelector("#product-jsonld")?.remove();
  if (metadata.structuredData) {
    const script = document.createElement("script");
    script.type = "application/ld+json";
    script.id = "product-jsonld";
    script.textContent = JSON.stringify(metadata.structuredData);
    document.head.append(script);
  }
}

function updateLocaleUrl() {
  const url = new URL(location.href);
  url.searchParams.set("lang", state.locale);
  history.replaceState(null, "", url);
}

function stateMessage(kind, { includeRetry = false } = {}) {
  const message = uiState(kind, state.locale);
  const role = kind === "error" ? "alert" : "status";
  const wrapper = document.createElement("div");
  wrapper.className = `intent-output cx-state cx-state-${kind}`;
  wrapper.setAttribute("role", role);
  wrapper.setAttribute("aria-live", kind === "error" ? "assertive" : "polite");
  wrapper.innerHTML = `<strong>${escapeHtml(message.title)}</strong><p>${escapeHtml(message.message)}</p>`;
  if (includeRetry && message.retry_label) {
    const retry = document.createElement("a");
    const url = new URL(location.href);
    url.searchParams.delete("product");
    url.searchParams.set("lang", state.locale);
    retry.className = "detail-link";
    retry.href = url.toString();
    retry.textContent = message.retry_label;
    wrapper.append(retry);
  }
  return wrapper;
}

function renderCatalog({ noticeKind = null } = {}) {
  state.flow = createCustomerFlow();
  productSection.hidden = true;
  catalogSection.hidden = false;
  catalogGrid.replaceChildren();
  catalogSummary.textContent = copy[state.locale].catalogCount(state.catalog.length);
  applyMetadata(catalogMetadata(state.locale));

  if (noticeKind) {
    catalogGrid.append(stateMessage(noticeKind));
  }

  if (state.catalog.length === 0) {
    catalogGrid.append(stateMessage("empty"));
    return;
  }

  for (const product of state.catalog) {
    const vm = catalogCardViewModel(product, state.locale);
    const node = cardTemplate.content.cloneNode(true);
    const article = node.querySelector("article");
    const availability = node.querySelector(".availability");
    availability.classList.add(vm.availability);
    availability.textContent = copy[state.locale][vm.availability] || copy[state.locale].unknown;
    node.querySelector("h3").textContent = vm.name;
    node.querySelector(".description").textContent = vm.shortDescription;
    node.querySelector(".price").textContent = vm.formattedPrice;
    const link = node.querySelector(".detail-link");
    link.href = vm.detailHref;
    link.textContent = copy[state.locale].view;
    link.setAttribute("aria-label", `${copy[state.locale].view}: ${vm.name}`);
    article.dataset.productKey = vm.productKey;
    catalogGrid.append(node);
  }
}

function localDateTimeToIso(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function feedbackList(items) {
  if (items.length === 0) return "";
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderDetail(product) {
  state.flow = transitionCustomerFlow(createCustomerFlow(), "select_product");
  const vm = productDetailViewModel(product, state.locale);
  catalogSection.hidden = true;
  productSection.hidden = false;
  productDetail.replaceChildren();
  applyMetadata(productMetadata(product, state.locale));

  const wrapper = document.createElement("div");
  wrapper.className = "detail-layout";
  wrapper.innerHTML = `
    <div class="detail-media" aria-label="${escapeHtml(vm.media[0]?.alt || vm.name)}">CX</div>
    <div class="detail-copy">
      <p class="availability ${escapeHtml(vm.availability)}">${escapeHtml(copy[state.locale][vm.availability] || copy[state.locale].unknown)}</p>
      <h1 id="product-title">${escapeHtml(vm.name)}</h1>
      <p class="lead">${escapeHtml(vm.description)}</p>
      <p><strong>${escapeHtml(vm.formattedPrice)}</strong></p>
      <p><strong>${escapeHtml(copy[state.locale].pickup)}:</strong> ${escapeHtml(vm.pickupInstructions)}</p>
      <section class="checkout-card" aria-labelledby="checkout-title">
        <h2 id="checkout-title">${escapeHtml(copy[state.locale].intentTitle)}</h2>
        <form id="checkout-form">
          <div class="form-grid">
            <div class="form-field">
              <label for="quantity">${escapeHtml(copy[state.locale].quantity)}</label>
              <input id="quantity" name="quantity" type="number" inputmode="numeric" min="1" value="1" required>
            </div>
            <div class="form-field">
              <label for="pickup-at">${escapeHtml(copy[state.locale].pickupTime)}</label>
              <input id="pickup-at" name="pickup-at" type="datetime-local">
            </div>
          </div>
          <p><button class="primary-button" type="submit">${escapeHtml(copy[state.locale].evaluate)}</button></p>
        </form>
        <div id="intent-output" class="intent-output" hidden role="status" aria-live="polite" aria-atomic="true"></div>
      </section>
    </div>`;
  productDetail.append(wrapper);

  document.querySelector("#checkout-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (["ready", "blocked"].includes(state.flow.state)) {
      state.flow = transitionCustomerFlow(state.flow, "edit_product");
    }
    state.flow = transitionCustomerFlow(state.flow, "start_checkout");

    const quantity = Number(document.querySelector("#quantity").value);
    const requestedPickupAt = localDateTimeToIso(document.querySelector("#pickup-at").value);
    const intent = buildCheckoutIntent({
      intentId: `cx-local-${vm.sku}`,
      locale: state.locale,
      sku: vm.sku,
      quantity,
      requestedPickupAt,
    });
    const evaluatedAt = new Date().toISOString();
    const pickupReadiness = evaluatePickupSelection(requestedPickupAt, evaluatedAt, state.pickupPolicy);
    const catalogBySku = new Map(state.catalog.map((item) => [item.sku, item]));
    const baseReadiness = evaluateCheckoutReadiness(intent, catalogBySku, evaluatedAt);
    const blockers = new Set(baseReadiness.blockers);
    if (!pickupReadiness.valid) blockers.add("pickup_time");
    const readiness = {
      ...baseReadiness,
      ready: baseReadiness.ready && pickupReadiness.valid,
      blockers: [...blockers].sort(),
      customer_action_required: blockers.has("pickup_time") ? ["select_pickup_time"] : baseReadiness.customer_action_required,
      mutation_authorized: false,
    };
    state.flow = transitionCustomerFlow(state.flow, readiness.ready ? "readiness_ready" : "readiness_blocked");

    const feedback = readinessFeedback(readiness, state.locale);
    const output = document.querySelector("#intent-output");
    output.hidden = false;
    const guidance = feedback.ready
      ? `<p>${escapeHtml(feedback.summary)}</p>`
      : `<p>${escapeHtml(feedback.summary)}</p><h3>${escapeHtml(copy[state.locale].nextSteps)}</h3>${feedbackList(feedback.action_messages.length ? feedback.action_messages : feedback.blocker_messages)}`;
    output.innerHTML = `
      <strong>${escapeHtml(readiness.ready ? copy[state.locale].ready : copy[state.locale].blocked)}</strong>
      ${guidance}
      <p>${escapeHtml(copy[state.locale].noOrder)}</p>
      <details>
        <summary>${escapeHtml(copy[state.locale].technicalDetails)}</summary>
        <pre></pre>
      </details>`;
    output.querySelector("pre").textContent = JSON.stringify(
      { flow: state.flow, intent, pickup_readiness: pickupReadiness, readiness, customer_feedback: feedback },
      null,
      2,
    );
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

function renderRoute() {
  setDocumentLocale();
  const params = new URLSearchParams(location.search);
  const productKey = params.get("product");
  if (!productKey) {
    renderCatalog();
    return;
  }
  const product = state.catalog.find((item) => item.product_key === productKey);
  if (!product) {
    history.replaceState(null, "", `?lang=${state.locale}`);
    renderCatalog({ noticeKind: "route_missing" });
    return;
  }
  renderDetail(product);
}

async function fetchFixture(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`fixture failed: ${response.status}`);
  const payload = await response.json();
  if (payload.fixture_only !== true) throw new Error("Sprint 4 preview requires fixture_only data");
  return payload;
}

async function boot() {
  setDocumentLocale();
  productSection.hidden = true;
  catalogSection.hidden = false;
  catalogGrid.replaceChildren(stateMessage("loading"));
  catalogSummary.textContent = "";
  applyMetadata(catalogMetadata(state.locale));

  const [catalogPayload, pickupPolicy] = await Promise.all([
    fetchFixture("./fixtures/catalog.json"),
    fetchFixture("./fixtures/pickup-policy.json"),
  ]);
  state.catalog = catalogPayload.products;
  state.pickupPolicy = pickupPolicy;
  renderRoute();

  localeSelect.addEventListener("change", () => {
    state.locale = normalizeLocale(localeSelect.value);
    updateLocaleUrl();
    renderRoute();
  });

  addEventListener("popstate", renderRoute);
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(() => undefined);
  }
}

boot().catch(() => {
  state.flow = transitionCustomerFlow(createCustomerFlow(), "fail");
  setDocumentLocale();
  applyMetadata(catalogMetadata(state.locale));
  productSection.hidden = true;
  catalogSection.hidden = false;
  catalogGrid.replaceChildren(stateMessage("error", { includeRetry: true }));
  catalogSummary.textContent = "";
});

import { localeHref } from "./locale-links.mjs";

const RETURN_TARGET_KEY = "phil-ai-os.cx.catalog-return-target.v1";

const copy = {
  en: {
    filtersLabel: "Product filters",
    all: "All products",
    available: "Available now",
    showing: (visible, total) => `Showing ${visible} of ${total}`,
    pickup: "Pickup supported",
    reviewCart: "Review cart",
    reviewCartHint: "Continue to the cart preview while keeping your language and selected product.",
    unavailableAction: "See available products",
    unavailableHint: "This item is currently unavailable. Choose another available product before continuing to cart.",
  },
  ja: {
    filtersLabel: "商品フィルター",
    all: "すべての商品",
    available: "現在購入可能",
    showing: (visible, total) => `${total}件中 ${visible}件を表示`,
    pickup: "店頭受取対応",
    reviewCart: "カートを確認",
    reviewCartHint: "言語設定と選択した商品を保ったままカートプレビューへ進みます。",
    unavailableAction: "購入可能な商品を見る",
    unavailableHint: "この商品は現在購入できません。カートへ進む前に、購入可能な商品を選択してください。",
  },
};

function filterFromUrl() {
  return new URLSearchParams(location.search).get("filter") === "available" ? "available" : "all";
}

let filterMode = filterFromUrl();
let returnFocusRestored = false;

function locale() {
  return document.documentElement.lang === "ja" ? "ja" : "en";
}

function productCards() {
  return [...document.querySelectorAll("#catalog-grid .product-card")];
}

function productKeyFromHref(href) {
  try {
    return new URL(href, location.href).searchParams.get("product");
  } catch {
    return null;
  }
}

function rememberCatalogReturnTarget(link) {
  const productKey = productKeyFromHref(link?.getAttribute("href") || link?.href || "");
  if (!productKey) return;
  try {
    sessionStorage.setItem(RETURN_TARGET_KEY, productKey);
  } catch {
    // Session storage is an optional UX enhancement only.
  }
}

function peekCatalogReturnTarget() {
  try {
    return sessionStorage.getItem(RETURN_TARGET_KEY);
  } catch {
    return null;
  }
}

function clearCatalogReturnTarget() {
  try {
    sessionStorage.removeItem(RETURN_TARGET_KEY);
  } catch {
    // No-op when storage is unavailable.
  }
}

function restoreCatalogReturnFocus() {
  if (returnFocusRestored || selectedProductKey()) return;
  const productKey = peekCatalogReturnTarget();
  if (!productKey) return;

  const targetLink = productCards()
    .filter((card) => !card.hidden)
    .map((card) => card.querySelector(".detail-link"))
    .find((link) => productKeyFromHref(link?.getAttribute("href") || link?.href || "") === productKey);

  if (!targetLink) return;
  const targetCard = targetLink.closest(".product-card");
  returnFocusRestored = true;
  clearCatalogReturnTarget();
  targetLink.focus({ preventScroll: true });
  targetCard?.scrollIntoView({ block: "center", inline: "nearest" });
}

function catalogReturnHref(lang = locale()) {
  const url = new URL("./", location.href);
  url.searchParams.set("lang", lang);
  if (filterMode === "available") url.searchParams.set("filter", "available");
  else url.searchParams.delete("filter");
  url.hash = "catalog-section";
  return `${url.pathname}${url.search}${url.hash}`;
}

function syncFilterUrl() {
  const url = new URL(location.href);
  if (filterMode === "available") url.searchParams.set("filter", "available");
  else url.searchParams.delete("filter");
  history.replaceState(null, "", url);
}

function decorateCatalogDetailLinks() {
  for (const card of productCards()) {
    const link = card.querySelector(".detail-link");
    if (!link) continue;
    const url = new URL(link.getAttribute("href") || link.href, location.href);
    if (filterMode === "available") url.searchParams.set("filter", "available");
    else url.searchParams.delete("filter");
    link.href = `${url.pathname}${url.search}${url.hash}`;
  }
}

function syncBackLink() {
  const back = document.querySelector("#back-link");
  if (!back) return;
  back.href = catalogReturnHref(locale());
}

function syncFilterControls() {
  const bar = document.querySelector("#browse-filter-bar");
  if (!bar) return;
  bar.querySelectorAll("[data-filter]").forEach((node) => {
    const active = node.dataset.filter === filterMode;
    node.classList.toggle("is-active", active);
    node.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function applyFilter() {
  const cards = productCards();
  let visible = 0;
  for (const card of cards) {
    const available = Boolean(card.querySelector(".availability.in_stock"));
    const show = filterMode === "all" || available;
    card.hidden = !show;
    if (show) visible += 1;
  }
  const summary = document.querySelector("#browse-filter-summary");
  if (summary) summary.textContent = copy[locale()].showing(visible, cards.length);
  syncFilterControls();
  decorateCatalogDetailLinks();
  syncBackLink();
  queueMicrotask(restoreCatalogReturnFocus);
}

function updateFilterCopy() {
  const lang = locale();
  const bar = document.querySelector("#browse-filter-bar");
  if (!bar) return;
  bar.setAttribute("aria-label", copy[lang].filtersLabel);
  const all = bar.querySelector('[data-filter="all"]');
  const available = bar.querySelector('[data-filter="available"]');
  if (all) all.textContent = copy[lang].all;
  if (available) available.textContent = copy[lang].available;
  applyFilter();
}

function ensureFilterBar() {
  const catalog = document.querySelector("#catalog-section");
  const grid = document.querySelector("#catalog-grid");
  if (!catalog || !grid || document.querySelector("#browse-filter-bar")) return;

  const wrapper = document.createElement("div");
  wrapper.className = "browse-controls";
  wrapper.innerHTML = `
    <div id="browse-filter-bar" class="filter-chip-row" role="group">
      <button class="filter-chip" type="button" data-filter="all" aria-controls="catalog-grid"></button>
      <button class="filter-chip" type="button" data-filter="available" aria-controls="catalog-grid"></button>
    </div>
    <p id="browse-filter-summary" class="browse-filter-summary" role="status" aria-live="polite" aria-atomic="true"></p>`;
  grid.before(wrapper);

  wrapper.addEventListener("click", (event) => {
    const detailLink = event.target.closest("#catalog-grid .detail-link");
    if (detailLink) {
      rememberCatalogReturnTarget(detailLink);
      return;
    }
    const button = event.target.closest("[data-filter]");
    if (!button) return;
    filterMode = button.dataset.filter === "available" ? "available" : "all";
    returnFocusRestored = false;
    syncFilterUrl();
    applyFilter();
  });
  updateFilterCopy();
}

function selectedProductKey() {
  return new URLSearchParams(location.search).get("product");
}

function selectedDetailIsAvailable(detail) {
  return Boolean(detail?.querySelector(".availability.in_stock"));
}

function syncDetailCheckoutAvailability(detail, available) {
  const checkout = detail?.querySelector(".checkout-card");
  if (!checkout) return;
  checkout.hidden = !available;
  checkout.setAttribute("aria-hidden", available ? "false" : "true");
  checkout.querySelectorAll("input, select, textarea, button").forEach((control) => {
    control.disabled = !available;
  });
}

function ensureDetailContinuation() {
  const section = document.querySelector("#product-section");
  const detail = document.querySelector("#product-detail");
  if (!section || !detail || section.hidden) return;
  let panel = document.querySelector("#mobile-detail-continuation");
  if (!panel) {
    panel = document.createElement("aside");
    panel.id = "mobile-detail-continuation";
    panel.className = "mobile-detail-continuation";
    panel.setAttribute("aria-live", "polite");
    panel.innerHTML = `<span class="mobile-detail-hint"></span><a class="detail-link mobile-detail-cart-link"></a>`;
    section.append(panel);
  }
  const lang = locale();
  const hint = panel.querySelector(".mobile-detail-hint");
  const link = panel.querySelector(".mobile-detail-cart-link");
  const available = selectedDetailIsAvailable(detail);
  syncDetailCheckoutAvailability(detail, available);
  syncBackLink();

  if (!available) {
    panel.dataset.detailMode = "browse_only";
    hint.textContent = copy[lang].unavailableHint;
    link.textContent = copy[lang].unavailableAction;
    link.classList.add("is-unavailable-redirect");
    filterMode = "available";
    link.href = catalogReturnHref(lang);
    link.removeAttribute("data-selected-product");
    return;
  }

  panel.dataset.detailMode = "checkout_preview";
  hint.textContent = copy[lang].reviewCartHint;
  link.textContent = copy[lang].reviewCart;
  link.classList.remove("is-unavailable-redirect");
  const cartUrl = new URL("./cart-preview.html", location.href);
  const productKey = selectedProductKey();
  if (productKey) {
    cartUrl.searchParams.set("product", productKey);
    link.dataset.selectedProduct = productKey;
  } else {
    link.removeAttribute("data-selected-product");
  }
  link.href = localeHref(`${cartUrl.pathname}${cartUrl.search}`, lang);
}

function refresh({ restoreFilterFromUrl = false } = {}) {
  if (restoreFilterFromUrl) {
    filterMode = filterFromUrl();
    returnFocusRestored = false;
  }
  ensureFilterBar();
  updateFilterCopy();
  ensureDetailContinuation();
  syncBackLink();
}

const catalog = document.querySelector("#catalog-grid");
if (catalog) {
  catalog.addEventListener("click", (event) => {
    const link = event.target.closest(".detail-link");
    if (link) rememberCatalogReturnTarget(link);
  });
  new MutationObserver(refresh).observe(catalog, { childList: true, subtree: true });
}
const detail = document.querySelector("#product-detail");
if (detail) new MutationObserver(refresh).observe(detail, { childList: true, subtree: true });
document.querySelector("#locale-select")?.addEventListener("change", () => queueMicrotask(refresh));
addEventListener("popstate", () => queueMicrotask(() => refresh({ restoreFilterFromUrl: true })));
refresh({ restoreFilterFromUrl: true });

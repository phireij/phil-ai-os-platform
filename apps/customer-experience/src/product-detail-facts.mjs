import { formatMoney, localized, normalizeLocale } from "./core.mjs";

const copy = {
  en: {
    label: "Product essentials",
    availability: "Availability",
    price: "Price",
    pickup: "Pickup",
    in_stock: "In stock",
    out_of_stock: "Out of stock",
    backorder: "Backorder",
    unknown: "Availability unknown",
    pickupYes: "Pickup supported",
    pickupNo: "Pickup unavailable",
  },
  ja: {
    label: "商品の基本情報",
    availability: "在庫状況",
    price: "価格",
    pickup: "店頭受取",
    in_stock: "在庫あり",
    out_of_stock: "在庫切れ",
    backorder: "入荷待ち",
    unknown: "在庫状況不明",
    pickupYes: "店頭受取対応",
    pickupNo: "店頭受取不可",
  },
};

function locale() {
  return normalizeLocale(document.documentElement.lang === "ja" ? "ja" : "en");
}

function selectedProductKey() {
  return new URLSearchParams(location.search).get("product");
}

async function loadFixtureProduct(productKey) {
  if (!productKey) return null;
  const response = await fetch("./fixtures/catalog.json", { cache: "no-store" });
  if (!response.ok) return null;
  const payload = await response.json();
  if (payload.fixture_only !== true || !Array.isArray(payload.products)) return null;
  return payload.products.find((product) => product.product_key === productKey) || null;
}

export function keyFactsForProduct(product, lang = locale()) {
  if (!product) return null;
  const c = copy[lang];
  const availability = c[product.availability] || c.unknown;
  return Object.freeze({
    label: c.label,
    availabilityLabel: c.availability,
    availability,
    availabilityState: product.availability || "unknown",
    priceLabel: c.price,
    price: formatMoney(product.price, lang),
    pickupLabel: c.pickup,
    pickup: product.pickup?.supported === true ? c.pickupYes : c.pickupNo,
    pickupSupported: product.pickup?.supported === true,
    mediaAlt: product.media?.[0]?.alt ? localized(product.media[0].alt, lang) : null,
  });
}

function renderFacts(product) {
  const detail = document.querySelector("#product-detail .detail-copy");
  if (!detail) return;
  const facts = keyFactsForProduct(product);
  if (!facts) return;

  const media = document.querySelector("#product-detail .detail-media");
  if (media && facts.mediaAlt) {
    media.setAttribute("role", "img");
    media.setAttribute("aria-label", facts.mediaAlt);
  }

  let list = detail.querySelector(".product-key-facts");
  if (!list) {
    list = document.createElement("dl");
    list.className = "product-key-facts";
    const lead = detail.querySelector(".lead");
    if (lead) detail.insertBefore(list, lead);
    else detail.prepend(list);
  }

  list.setAttribute("aria-label", facts.label);
  list.innerHTML = `
    <div class="product-key-fact">
      <dt>${facts.availabilityLabel}</dt>
      <dd class="availability ${facts.availabilityState}">${facts.availability}</dd>
    </div>
    <div class="product-key-fact">
      <dt>${facts.priceLabel}</dt>
      <dd class="product-key-price">${facts.price}</dd>
    </div>
    <div class="product-key-fact">
      <dt>${facts.pickupLabel}</dt>
      <dd data-pickup-supported="${facts.pickupSupported}">${facts.pickup}</dd>
    </div>`;
}

let renderToken = 0;

export async function refreshProductKeyFacts() {
  const token = ++renderToken;
  const productKey = selectedProductKey();
  const section = document.querySelector("#product-section");
  if (!productKey || !section || section.hidden) return;
  const product = await loadFixtureProduct(productKey);
  if (token !== renderToken || !product) return;
  renderFacts(product);
}

const detailRoot = document.querySelector("#product-detail");
if (detailRoot) {
  new MutationObserver(() => queueMicrotask(refreshProductKeyFacts)).observe(detailRoot, { childList: true, subtree: true });
}
document.querySelector("#locale-select")?.addEventListener("change", () => queueMicrotask(refreshProductKeyFacts));
addEventListener("popstate", () => queueMicrotask(refreshProductKeyFacts));
queueMicrotask(refreshProductKeyFacts);

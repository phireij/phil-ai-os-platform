import { syncLocaleLinks } from "./locale-links.mjs";

const copy = {
  en: {
    eyebrow: "Before you continue",
    title: "You stay in control before the final action",
    orderTitle: "Review your order",
    orderCopy: "Check products, quantities and the running total on your phone.",
    fulfillmentTitle: "Confirm pickup or shipping",
    fulfillmentCopy: "The final experience must show the applicable shipping fee before order submission.",
    paymentTitle: "Confirm payment details",
    paymentCopy: "Payment method and timing are reviewed before the final order action.",
    reassurance: "You will still review the final information before any order-submission action.",
    shop: "Shop",
    cart: "Cart",
    pickup: "Pickup",
    nav: "Mobile checkout navigation",
  },
  ja: {
    eyebrow: "次へ進む前に",
    title: "最終操作の前に、内容を確認できます",
    orderTitle: "注文内容を確認",
    orderCopy: "商品・数量・合計金額をスマートフォンで確認できます。",
    fulfillmentTitle: "店頭受取または配送を確認",
    fulfillmentCopy: "最終画面では注文送信前に適用される送料を表示する必要があります。",
    paymentTitle: "支払情報を確認",
    paymentCopy: "最終注文操作の前に支払方法と支払時期を確認します。",
    reassurance: "注文送信の操作前に、最終情報をもう一度確認できます。",
    shop: "商品",
    cart: "カート",
    pickup: "受取",
    nav: "モバイルチェックアウトナビゲーション",
  },
};

const selectors = {
  "#confidence-eyebrow": "eyebrow",
  "#confidence-title": "title",
  "#confidence-order-title": "orderTitle",
  "#confidence-order-copy": "orderCopy",
  "#confidence-fulfillment-title": "fulfillmentTitle",
  "#confidence-fulfillment-copy": "fulfillmentCopy",
  "#confidence-payment-title": "paymentTitle",
  "#confidence-payment-copy": "paymentCopy",
  "#checkout-reassurance": "reassurance",
  "#dock-shop-label": "shop",
  "#dock-cart-label": "cart",
  "#dock-pickup-label": "pickup",
};

function apply(locale) {
  const lang = locale === "ja" ? "ja" : "en";
  for (const [selector, key] of Object.entries(selectors)) {
    const node = document.querySelector(selector);
    if (node) node.textContent = copy[lang][key];
  }
  document.querySelector(".mobile-action-dock")?.setAttribute("aria-label", copy[lang].nav);
  syncLocaleLinks(lang);
}

const localeSelect = document.querySelector("#locale-select");
localeSelect?.addEventListener("change", () => queueMicrotask(() => apply(localeSelect.value)));
const requestedLocale = new URLSearchParams(location.search).get("lang");
apply(requestedLocale || document.documentElement.lang);

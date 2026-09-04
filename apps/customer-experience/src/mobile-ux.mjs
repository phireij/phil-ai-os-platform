const localized = {
  en: {
    browseProducts: "Browse products",
    reviewCart: "Review cart flow",
    journeyEyebrow: "Simple ordering",
    journeyTitle: "From craving to confirmation",
    browseTitle: "Choose your favorites",
    browseCopy: "Browse clear product details, price and availability.",
    fulfillmentTitle: "Choose fulfillment",
    fulfillmentCopy: "See pickup and delivery guidance before checkout.",
    reviewTitle: "Review before submitting",
    reviewCopy: "Confirm item, price, shipping and payment details before the final action.",
    previewsEyebrow: "Customer-flow previews",
    previewsTitle: "Review the journey",
    cartTitle: "Cart & payment handoff",
    cartCopy: "Review order guidance and payment-method presentation.",
    confirmationTitle: "Final confirmation",
    confirmationCopy: "Review the final-order information hierarchy before submission.",
    pickupTitle: "Quick Pickup",
    pickupCopy: "Review the fail-closed Quick Pickup readiness experience.",
    shop: "Shop",
    cart: "Cart",
    pickup: "Pickup",
    navLabel: "Mobile preview navigation",
  },
  ja: {
    browseProducts: "商品を見る",
    reviewCart: "カートの流れを確認",
    journeyEyebrow: "かんたん注文",
    journeyTitle: "商品選びから最終確認まで",
    browseTitle: "お気に入りを選ぶ",
    browseCopy: "商品情報・価格・在庫状況を分かりやすく確認できます。",
    fulfillmentTitle: "受取方法を選ぶ",
    fulfillmentCopy: "チェックアウト前に店頭受取・配送の案内を確認できます。",
    reviewTitle: "送信前に最終確認",
    reviewCopy: "商品・価格・送料・支払情報を最終操作の前に確認できます。",
    previewsEyebrow: "お客様向けフロー",
    previewsTitle: "注文の流れを確認",
    cartTitle: "カート・決済引継ぎ",
    cartCopy: "注文案内と支払方法の表示を確認します。",
    confirmationTitle: "最終確認",
    confirmationCopy: "注文送信前に表示される情報の構成を確認します。",
    pickupTitle: "クイックピックアップ",
    pickupCopy: "安全側に停止するクイックピックアップ準備画面を確認します。",
    shop: "商品",
    cart: "カート",
    pickup: "受取",
    navLabel: "モバイルプレビューナビゲーション",
  },
};

const selectors = {
  ".hero-actions .detail-link": "browseProducts",
  ".hero-actions .secondary-link": "reviewCart",
  ".journey-panel .eyebrow": "journeyEyebrow",
  "#journey-title": "journeyTitle",
  "#journey-browse-title": "browseTitle",
  "#journey-browse-copy": "browseCopy",
  "#journey-fulfillment-title": "fulfillmentTitle",
  "#journey-fulfillment-copy": "fulfillmentCopy",
  "#journey-review-title": "reviewTitle",
  "#journey-review-copy": "reviewCopy",
  ".preview-links > .eyebrow": "previewsEyebrow",
  "#preview-links-title": "previewsTitle",
  ".preview-link-card:nth-child(1) strong": "cartTitle",
  ".preview-link-card:nth-child(1) span": "cartCopy",
  ".preview-link-card:nth-child(2) strong": "confirmationTitle",
  ".preview-link-card:nth-child(2) span": "confirmationCopy",
  ".preview-link-card:nth-child(3) strong": "pickupTitle",
  ".preview-link-card:nth-child(3) span": "pickupCopy",
  "#dock-shop-label": "shop",
  "#dock-cart-label": "cart",
  "#dock-pickup-label": "pickup",
};

function currentLocale() {
  return document.documentElement.lang === "ja" ? "ja" : "en";
}

export function applyMobileUxLocale(locale = currentLocale()) {
  const lang = locale === "ja" ? "ja" : "en";
  const copy = localized[lang];
  for (const [selector, key] of Object.entries(selectors)) {
    const node = document.querySelector(selector);
    if (node) node.textContent = copy[key];
  }
  const nav = document.querySelector(".mobile-action-dock");
  if (nav) nav.setAttribute("aria-label", copy.navLabel);
  document.querySelectorAll(".pickup-chip").forEach((node) => {
    node.textContent = copy.pickup;
  });
}

const localeSelect = document.querySelector("#locale-select");
localeSelect?.addEventListener("change", () => queueMicrotask(() => applyMobileUxLocale(localeSelect.value)));

const catalog = document.querySelector("#catalog-grid");
if (catalog) {
  new MutationObserver(() => applyMobileUxLocale()).observe(catalog, { childList: true, subtree: true });
}

applyMobileUxLocale();

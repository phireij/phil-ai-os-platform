import { syncLocaleLinks } from "./locale-links.mjs";

const copy = Object.freeze({
  en: Object.freeze({
    nav: "Final review navigation",
    shop: "Shop",
    edit: "Edit cart",
    review: "Review",
  }),
  ja: Object.freeze({
    nav: "最終確認ナビゲーション",
    shop: "商品",
    edit: "カート修正",
    review: "確認",
  }),
});

function locale() {
  return document.documentElement.lang === "ja" ? "ja" : "en";
}

export function updateFinalReviewNavigation() {
  const lang = locale();
  const nav = document.querySelector("#final-review-mobile-nav");
  if (!nav) return;
  nav.setAttribute("aria-label", copy[lang].nav);
  document.querySelector("#final-review-shop-label")?.replaceChildren(copy[lang].shop);
  document.querySelector("#final-review-edit-label")?.replaceChildren(copy[lang].edit);
  document.querySelector("#final-review-current-label")?.replaceChildren(copy[lang].review);
  syncLocaleLinks(lang, nav);
  syncLocaleLinks(lang, document.querySelector("main"));
}

function install() {
  updateFinalReviewNavigation();
  document.querySelector("#locale-select")?.addEventListener("change", () => queueMicrotask(updateFinalReviewNavigation));
}

if (typeof document !== "undefined") install();

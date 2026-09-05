const copy = Object.freeze({
  en: Object.freeze({
    skip: "Skip to content",
    language: "Language",
    status: Object.freeze({
      catalog: "Isolated preview · No live checkout",
      cart: "Isolated preview · KOMOJU not connected",
      confirmation: "Isolated synthetic preview · No order submission",
      pickup: "Isolated preview · No external activation",
    }),
    footer: Object.freeze({
      catalog: "Phil AI OS · Sprint 4 Customer Experience · synthetic fixture environment",
      cart: "Phil AI OS · Sprint 4 · synthetic cart/payment-handoff environment",
      confirmation: "Phil AI OS · Sprint 4 · synthetic final-confirmation compliance preview",
      pickup: "Phil AI OS · Sprint 4 Customer Experience · fixture-only Quick Pickup readiness",
    }),
    metadata: Object.freeze({
      cart: Object.freeze({
        title: "Phil AI OS — Cart & KOMOJU Handoff Preview",
        description: "Phil AI OS isolated multi-item checkout and KOMOJU handoff preview",
      }),
      confirmation: Object.freeze({
        title: "Phil AI OS — Final Confirmation Preview",
        description: "Phil AI OS isolated final order confirmation compliance preview",
      }),
      pickup: Object.freeze({
        title: "Phil AI OS — Quick Pickup Readiness Preview",
        description: "Phil AI OS isolated Air Mobile Quick Pickup readiness preview",
      }),
    }),
  }),
  ja: Object.freeze({
    skip: "メインコンテンツへ移動",
    language: "言語",
    status: Object.freeze({
      catalog: "隔離プレビュー · ライブチェックアウトなし",
      cart: "隔離プレビュー · KOMOJU未接続",
      confirmation: "隔離された合成プレビュー · 注文送信なし",
      pickup: "隔離プレビュー · 外部有効化なし",
    }),
    footer: Object.freeze({
      catalog: "Phil AI OS · Sprint 4 カスタマー体験 · 合成フィクスチャ環境",
      cart: "Phil AI OS · Sprint 4 · 合成カート・決済引継ぎ環境",
      confirmation: "Phil AI OS · Sprint 4 · 合成最終確認コンプライアンスプレビュー",
      pickup: "Phil AI OS · Sprint 4 カスタマー体験 · フィクスチャ専用クイックピックアップ準備状況",
    }),
    metadata: Object.freeze({
      cart: Object.freeze({
        title: "Phil AI OS — カート・KOMOJU引継ぎプレビュー",
        description: "Phil AI OS の分離された複数商品チェックアウトとKOMOJU引継ぎプレビュー",
      }),
      confirmation: Object.freeze({
        title: "Phil AI OS — 注文最終確認プレビュー",
        description: "Phil AI OS の分離された注文最終確認コンプライアンスプレビュー",
      }),
      pickup: Object.freeze({
        title: "Phil AI OS — クイックピックアップ準備状況プレビュー",
        description: "Phil AI OS の分離されたAir モバイルオーダー・クイックピックアップ準備状況プレビュー",
      }),
    }),
  }),
});

function normalizeLocale(locale) {
  return locale === "ja" ? "ja" : "en";
}

export function pageChromeKey(pathname = "/") {
  const path = String(pathname || "/").split("?")[0];
  if (path.endsWith("/cart-preview.html")) return "cart";
  if (path.endsWith("/confirmation-preview.html")) return "confirmation";
  if (path.endsWith("/quick-pickup-preview.html")) return "pickup";
  return "catalog";
}

export function applyPageChromeLocale(locale = document.documentElement.lang) {
  const lang = normalizeLocale(locale);
  const localized = copy[lang];
  const page = pageChromeKey(typeof location !== "undefined" ? location.pathname : "/");
  const skipLink = document.querySelector(".skip-link");
  const languageLabel = document.querySelector('.locale-label[for="locale-select"]');
  const localeSelect = document.querySelector("#locale-select");
  const statusPill = document.querySelector(".status-pill");
  const footerCopy = document.querySelector("footer p");
  const metadata = localized.metadata?.[page];

  if (skipLink) skipLink.textContent = localized.skip;
  if (languageLabel) languageLabel.textContent = localized.language;
  if (localeSelect) localeSelect.setAttribute("aria-label", localized.language);
  if (statusPill) statusPill.textContent = localized.status[page];
  if (footerCopy) footerCopy.textContent = localized.footer[page];
  if (metadata) {
    document.title = metadata.title;
    document.querySelector('meta[name="description"]')?.setAttribute("content", metadata.description);
  }
}

if (typeof document !== "undefined") {
  const localeSelect = document.querySelector("#locale-select");
  localeSelect?.addEventListener("change", () => {
    queueMicrotask(() => applyPageChromeLocale(localeSelect.value));
  });

  if (typeof MutationObserver !== "undefined") {
    new MutationObserver(() => applyPageChromeLocale(document.documentElement.lang)).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["lang"],
    });
  }

  applyPageChromeLocale();
}

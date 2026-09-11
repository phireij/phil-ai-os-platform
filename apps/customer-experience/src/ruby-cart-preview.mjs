import "./ruby-storefront-progress.mjs";
import { formatRubyYen, normalizeRubyLocale } from "./ruby-working-product-detail.mjs";
import {
  clearPreviewCart,
  previewCartSummary,
  removePreviewCartItem,
  setPreviewCartQuantity,
} from "./ruby-preview-cart.mjs";

const root = document.querySelector("#ruby-preview-cart-root");
const localeSelect = document.querySelector("#ruby-locale");

const copy = Object.freeze({
  en: Object.freeze({
    eyebrow: "Session-only preview",
    title: "Preview cart",
    intro: "Review local working-catalog selections. This cart is isolated from WooCommerce and cannot submit an order.",
    emptyTitle: "Your preview cart is empty.",
    emptyCopy: "Open a working product detail and add a source-backed selection to this local session cart.",
    continueShopping: "Continue working selection",
    quantity: "Quantity",
    remove: "Remove",
    itemTotal: "Line total",
    total: "Preview total",
    clear: "Clear preview cart",
    localNote: "Selections are stored only for this browser session. Prices are re-read from the bounded working catalog each time this page renders.",
    fallback: "Japanese product copy remains owner-gated; approved English product names are shown.",
    storageTitle: "Preview cart unavailable",
    storageCopy: "Session storage is unavailable in this browser context. No order or remote data was created.",
    unsafeTitle: "Preview boundary check failed",
    unsafeCopy: "The local cart is hidden because the working-catalog authority state is not safe for this preview.",
    boundaryTitle: "Pre-production boundary",
    boundaryCopy: "Checkout, live availability, shipping calculation, order creation, payment, SMS, inventory mutation, and WooCommerce publication are intentionally unavailable here.",
  }),
  ja: Object.freeze({
    eyebrow: "セッション限定プレビュー",
    title: "プレビューカート",
    intro: "作業中カタログの商品をローカルで確認するためのカートです。WooCommerceとは分離されており、注文を送信できません。",
    emptyTitle: "プレビューカートは空です。",
    emptyCopy: "作業中の商品詳細を開き、ソースに基づく商品をこのローカルセッションのカートに追加してください。",
    continueShopping: "作業中の商品一覧へ戻る",
    quantity: "数量",
    remove: "削除",
    itemTotal: "小計",
    total: "プレビュー合計",
    clear: "プレビューカートを空にする",
    localNote: "選択内容はこのブラウザセッション内だけに保存されます。価格は画面表示のたびに限定された作業中カタログから再取得されます。",
    fallback: "日本語の商品コピーはオーナー承認待ちのため、承認済みの英語商品名を表示しています。",
    storageTitle: "プレビューカートを利用できません",
    storageCopy: "このブラウザ環境ではセッションストレージを利用できません。注文や外部データは作成されていません。",
    unsafeTitle: "プレビュー境界チェックに失敗しました",
    unsafeCopy: "作業中カタログの権限状態が安全条件を満たさないため、ローカルカートを表示していません。",
    boundaryTitle: "プレプロダクション境界",
    boundaryCopy: "チェックアウト、リアルタイム在庫、送料計算、注文作成、決済、SMS、在庫変更、WooCommerce公開は意図的に利用できません。",
  }),
});

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function updateStaticCopy(lang) {
  document.querySelector("#ruby-cart-eyebrow").textContent = copy[lang].eyebrow;
  document.querySelector("#ruby-cart-title").textContent = copy[lang].title;
  document.querySelector("#ruby-cart-intro").textContent = copy[lang].intro;
  document.querySelector("#ruby-cart-boundary-title").textContent = copy[lang].boundaryTitle;
  document.querySelector("#ruby-cart-boundary-copy").textContent = copy[lang].boundaryCopy;
  document.title = `Ruby's Cake Delights — ${copy[lang].title}`;
}

function renderMessage(title, text, lang) {
  root.replaceChildren();
  const card = element("div", "ruby-cart-empty");
  card.append(element("h2", null, title), element("p", null, text));
  const back = element("a", "button secondary", copy[lang].continueShopping);
  back.href = `./ruby-storefront-progress.html?lang=${lang}#favorites`;
  card.append(back);
  root.append(card);
  root.setAttribute("aria-busy", "false");
}

function lineName(line, lang) {
  return lang === "ja" && line.japaneseName ? line.japaneseName : line.englishName;
}

function renderCart(locale = document.documentElement.lang) {
  const lang = normalizeRubyLocale(locale);
  updateStaticCopy(lang);

  let summary;
  try {
    summary = previewCartSummary();
  } catch {
    renderMessage(copy[lang].storageTitle, copy[lang].storageCopy, lang);
    return;
  }

  if (!summary.previewOnly || summary.catalogApproved || summary.mutationAuthorized || summary.productionPublishAuthorized) {
    renderMessage(copy[lang].unsafeTitle, copy[lang].unsafeCopy, lang);
    return;
  }

  if (!summary.lines.length) {
    renderMessage(copy[lang].emptyTitle, copy[lang].emptyCopy, lang);
    return;
  }

  root.replaceChildren();
  const panel = element("div", "ruby-cart-panel");
  const lines = element("div", "ruby-cart-lines");

  for (const line of summary.lines) {
    const article = element("article", "ruby-cart-line");
    const info = element("div");
    info.append(element("h2", null, lineName(line, lang)));
    const meta = [];
    if (line.sizeCm) meta.push(`${line.sizeCm} cm`);
    meta.push(line.sku);
    info.append(element("p", "ruby-cart-line-meta", meta.join(" · ")));

    const price = element("div", "ruby-cart-line-price", `${formatRubyYen(line.unitPriceJpy)} × ${line.quantity}`);
    price.append(element("span", "ruby-cart-line-total", `${copy[lang].itemTotal}: ${formatRubyYen(line.lineTotalJpy)}`));
    article.append(info, price);

    const controls = element("div", "ruby-cart-line-controls");
    const minus = element("button", "ruby-cart-qty-button", "−");
    minus.type = "button";
    minus.setAttribute("aria-label", `${copy[lang].quantity} - 1`);
    const qty = element("span", "ruby-cart-qty", `${copy[lang].quantity}: ${line.quantity}`);
    const plus = element("button", "ruby-cart-qty-button", "+");
    plus.type = "button";
    plus.setAttribute("aria-label", `${copy[lang].quantity} + 1`);
    const remove = element("button", "ruby-cart-remove", copy[lang].remove);
    remove.type = "button";

    minus.addEventListener("click", () => {
      try { setPreviewCartQuantity(line.lineKey, Math.max(0, line.quantity - 1)); } catch {}
      renderCart(lang);
    });
    plus.addEventListener("click", () => {
      try { setPreviewCartQuantity(line.lineKey, line.quantity + 1); } catch {}
      renderCart(lang);
    });
    remove.addEventListener("click", () => {
      try { removePreviewCartItem(line.lineKey); } catch {}
      renderCart(lang);
    });

    controls.append(minus, qty, plus, remove);
    article.append(controls);
    lines.append(article);
  }

  panel.append(lines);
  const summaryRow = element("div", "ruby-cart-summary");
  summaryRow.append(element("span", "ruby-cart-total-label", copy[lang].total), element("span", "ruby-cart-total", formatRubyYen(summary.totalJpy)));
  panel.append(summaryRow);

  const actions = element("div", "ruby-cart-actions");
  const continueLink = element("a", "button secondary", copy[lang].continueShopping);
  continueLink.href = `./ruby-storefront-progress.html?lang=${lang}#favorites`;
  const clearButton = element("button", "ruby-cart-clear", copy[lang].clear);
  clearButton.type = "button";
  clearButton.addEventListener("click", () => {
    try { clearPreviewCart(); } catch {}
    renderCart(lang);
  });
  actions.append(continueLink, clearButton);
  panel.append(actions);
  panel.append(element("p", "ruby-cart-note", copy[lang].localNote));
  if (lang === "ja" && summary.lines.some((line) => !line.japaneseName)) {
    panel.append(element("p", "copy-pending", copy[lang].fallback));
  }

  root.append(panel);
  root.setAttribute("aria-busy", "false");
}

renderCart();
localeSelect.addEventListener("change", () => renderCart(localeSelect.value));

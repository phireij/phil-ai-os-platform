import "./ruby-storefront-progress.mjs";
import { normalizeRubyLocale, workingProductDetailModel } from "./ruby-working-product-detail.mjs";

const detailRoot = document.querySelector("#ruby-product-detail");
const localeSelect = document.querySelector("#ruby-locale");
const backLink = document.querySelector("#ruby-product-back");

const copy = Object.freeze({
  en: Object.freeze({
    back: "← Back to working selection",
    notFoundTitle: "This working product is not available in the bounded preview.",
    notFoundCopy: "Return to the storefront to choose from the current source-backed working selection.",
    detailEyebrow: "Source-backed working product",
    fulfillmentTitle: "Fulfillment status",
    variantsTitle: "Working size options",
    variantSku: "Working SKU",
    boundaryTitle: "Pre-production boundary",
    boundaryCopy: "This page does not show live availability and cannot create an order, charge a payment, send SMS, change inventory, or publish WooCommerce data.",
    unavailableTitle: "Preview boundary check failed.",
    unavailableCopy: "This product detail is hidden because the bounded working-catalog authority state is no longer safe for this preview.",
  }),
  ja: Object.freeze({
    back: "← 作業中の商品一覧へ戻る",
    notFoundTitle: "この商品は現在の限定プレビューにはありません。",
    notFoundCopy: "ストア画面に戻り、現在のソースに基づく作業中商品から選択してください。",
    detailEyebrow: "ソースに基づく作業中商品",
    fulfillmentTitle: "受取・配送ステータス",
    variantsTitle: "作業中サイズオプション",
    variantSku: "作業中SKU",
    boundaryTitle: "プレプロダクション境界",
    boundaryCopy: "この画面はリアルタイム在庫を表示せず、注文作成、決済、SMS送信、在庫変更、WooCommerce公開を実行できません。",
    unavailableTitle: "プレビュー境界チェックに失敗しました。",
    unavailableCopy: "作業中カタログの権限状態がこのプレビューの安全条件を満たさないため、商品詳細を表示していません。",
  }),
});

function currentProductKey() {
  return new URLSearchParams(location.search).get("product");
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function setBackLink(locale) {
  const lang = normalizeRubyLocale(locale);
  backLink.textContent = copy[lang].back;
  backLink.href = `./ruby-storefront-progress.html?lang=${lang}#favorites`;
}

function renderMessage(title, body, locale) {
  detailRoot.replaceChildren();
  detailRoot.className = "ruby-product-detail ruby-product-message";
  detailRoot.append(element("h1", null, title), element("p", null, body));
  detailRoot.setAttribute("aria-busy", "false");
  document.title = `Ruby's Cake Delights — ${title}`;
  setBackLink(locale);
}

function renderProduct(locale = document.documentElement.lang) {
  const lang = normalizeRubyLocale(locale);
  const model = workingProductDetailModel(currentProductKey(), lang);
  if (!model) {
    renderMessage(copy[lang].notFoundTitle, copy[lang].notFoundCopy, lang);
    return;
  }
  if (!model.previewOnly || model.catalogApproved || model.mutationAuthorized || model.productionPublishAuthorized) {
    renderMessage(copy[lang].unavailableTitle, copy[lang].unavailableCopy, lang);
    return;
  }

  detailRoot.replaceChildren();
  detailRoot.className = "ruby-product-detail";
  setBackLink(lang);

  const visual = element("div", "ruby-product-detail-visual");
  const initial = element("span", null, model.name.charAt(0).toUpperCase());
  initial.setAttribute("aria-hidden", "true");
  const chip = element("span", "working-chip", model.workingPreviewLabel);
  visual.append(initial, chip);

  const body = element("div", "ruby-product-detail-body");
  body.append(element("p", "eyebrow", copy[lang].detailEyebrow));
  body.append(element("h1", null, model.name));
  body.append(element("p", "ruby-product-detail-price", model.price));
  body.append(element("p", "ruby-product-detail-description", model.description));

  if (model.fallbackMessage) {
    body.append(element("p", "copy-pending", model.fallbackMessage));
  }

  if (model.variants.length) {
    const variants = element("section", "ruby-product-variants");
    variants.append(element("h2", null, copy[lang].variantsTitle));
    const list = element("div", "ruby-product-variant-list");
    for (const variant of model.variants) {
      const row = element("div", "ruby-product-variant");
      row.append(element("strong", null, `${variant.sizeCm} cm`));
      row.append(element("span", null, variant.price));
      row.append(element("small", null, `${copy[lang].variantSku}: ${variant.sku}`));
      list.append(row);
    }
    variants.append(list);
    body.append(variants);
  }

  const fulfillment = element("section", "ruby-product-fulfillment");
  fulfillment.append(element("h2", null, copy[lang].fulfillmentTitle));
  fulfillment.append(element("p", null, model.fulfillment));
  fulfillment.append(element("p", "copy-pending", model.fulfillmentCaution));
  body.append(fulfillment);

  const boundary = element("section", "ruby-product-boundary");
  boundary.append(element("strong", null, copy[lang].boundaryTitle));
  boundary.append(element("p", null, copy[lang].boundaryCopy));
  body.append(boundary);

  detailRoot.append(visual, body);
  detailRoot.setAttribute("aria-busy", "false");
  document.title = `Ruby's Cake Delights — ${model.name}`;
}

renderProduct();
localeSelect.addEventListener("change", () => renderProduct(localeSelect.value));

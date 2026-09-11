import "./ruby-storefront-progress.mjs";
import { normalizeRubyLocale, workingProductDetailModel } from "./ruby-working-product-detail.mjs";
import { addPreviewCartItem } from "./ruby-preview-cart.mjs";

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
    cartTitle: "Local preview cart",
    sizeLabel: "Choose a working size",
    sizePlaceholder: "Select size",
    addToCart: "Add to preview cart",
    added: "Added to the local preview cart. No order was created.",
    chooseSize: "Choose a size before adding this product.",
    cartUnavailable: "Local preview cart storage is unavailable in this browser session.",
    viewCart: "View preview cart",
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
    cartTitle: "ローカル・プレビューカート",
    sizeLabel: "作業中サイズを選択",
    sizePlaceholder: "サイズを選択",
    addToCart: "プレビューカートに追加",
    added: "ローカル・プレビューカートに追加しました。注文は作成されていません。",
    chooseSize: "カートに追加する前にサイズを選択してください。",
    cartUnavailable: "このブラウザセッションではローカル・プレビューカートを利用できません。",
    viewCart: "プレビューカートを見る",
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

function renderPreviewCartControls(body, model, lang) {
  const section = element("section", "ruby-product-cart-controls");
  section.append(element("h2", null, copy[lang].cartTitle));

  let variantSelect = null;
  if (model.variants.length) {
    const label = element("label", "ruby-product-cart-label", copy[lang].sizeLabel);
    variantSelect = document.createElement("select");
    variantSelect.className = "ruby-product-cart-select";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = copy[lang].sizePlaceholder;
    placeholder.disabled = true;
    placeholder.selected = true;
    variantSelect.append(placeholder);
    for (const variant of model.variants) {
      const option = document.createElement("option");
      option.value = variant.sku;
      option.textContent = `${variant.sizeCm} cm · ${variant.price}`;
      variantSelect.append(option);
    }
    label.append(variantSelect);
    section.append(label);
  }

  const actions = element("div", "ruby-product-cart-actions");
  const addButton = element("button", "button primary", copy[lang].addToCart);
  addButton.type = "button";
  const viewCart = element("a", "button secondary", copy[lang].viewCart);
  viewCart.href = `./ruby-cart-preview.html?lang=${lang}`;
  actions.append(addButton, viewCart);
  section.append(actions);

  const status = element("p", "ruby-product-cart-status");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  section.append(status);

  addButton.addEventListener("click", () => {
    const variantSku = variantSelect ? variantSelect.value : null;
    if (variantSelect && !variantSku) {
      status.textContent = copy[lang].chooseSize;
      return;
    }
    try {
      addPreviewCartItem({ productKey: model.key, variantSku });
      status.textContent = copy[lang].added;
    } catch {
      status.textContent = copy[lang].cartUnavailable;
    }
  });

  body.append(section);
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

  renderPreviewCartControls(body, model, lang);

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

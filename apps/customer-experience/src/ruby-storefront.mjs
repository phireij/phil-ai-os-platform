import "./ruby-storefront-progress.mjs";
import { workingCatalogPreview } from "./ruby-working-catalog-preview.mjs";

const localeSelect = document.querySelector("#ruby-locale");
const productGrid = document.querySelector("#ruby-working-products");

const labels = {
  en: {
    workingPreview: "Working preview",
    fromPrice: "From",
    workingPrice: "Working catalog price",
    pendingCopy: "Japanese product name and description remain owner-gated. The approved English source copy is shown without inventing a translation.",
  },
  ja: {
    workingPreview: "作業中プレビュー",
    fromPrice: "〜",
    workingPrice: "作業中カタログ価格",
    pendingCopy: "日本語の商品名・商品説明はオーナー承認待ちです。未承認の翻訳は作成せず、承認済みの英語原文を表示しています。",
  },
};

function normalizeLocale(value) {
  return value === "ja" ? "ja" : "en";
}

function formatYen(value) {
  return `¥${Number(value).toLocaleString("en-US")}`;
}

function productArtClass(product) {
  if (product.form === "Rectangle") return "product-art bar";
  if (product.family === "Bread") return "product-art bread";
  return "product-art";
}

function variantSummary(product) {
  return product.variants
    .map((variant) => `${variant.size_cm} cm ${formatYen(variant.price_jpy)}`)
    .join(" · ");
}

export function renderWorkingCatalog(locale = document.documentElement.lang) {
  const selected = normalizeLocale(locale);
  productGrid.replaceChildren();

  for (const product of workingCatalogPreview.products) {
    const article = document.createElement("article");
    article.className = "product-card";
    article.dataset.productKey = product.key;

    const art = document.createElement("div");
    art.className = productArtClass(product);
    const initial = document.createElement("span");
    initial.setAttribute("aria-hidden", "true");
    initial.textContent = product.english_name.charAt(0).toUpperCase();
    const chip = document.createElement("span");
    chip.className = "working-chip";
    chip.textContent = labels[selected].workingPreview;
    art.append(initial, chip);

    const body = document.createElement("div");
    body.className = "product-body";
    const heading = document.createElement("h3");
    heading.textContent = selected === "ja" && product.japanese_name ? product.japanese_name : product.english_name;
    const description = document.createElement("p");
    description.textContent = selected === "ja" && product.japanese_description
      ? product.japanese_description
      : product.english_description;

    const price = document.createElement("div");
    price.className = "product-price";
    const priceValue = document.createElement("span");
    if (product.price_mode === "from") {
      priceValue.textContent = selected === "ja"
        ? `${formatYen(product.price_jpy)}${labels[selected].fromPrice}`
        : `${labels[selected].fromPrice} ${formatYen(product.price_jpy)}`;
    } else {
      priceValue.textContent = formatYen(product.price_jpy);
    }
    const priceNote = document.createElement("small");
    priceNote.textContent = product.product_type === "variable"
      ? variantSummary(product)
      : labels[selected].workingPrice;
    price.append(priceValue, priceNote);

    body.append(heading, description, price);
    if (!product.japanese_name || !product.japanese_description) {
      const pending = document.createElement("p");
      pending.className = "copy-pending";
      pending.textContent = labels[selected].pendingCopy;
      body.append(pending);
    }

    article.append(art, body);
    productGrid.append(article);
  }

  productGrid.setAttribute("aria-busy", "false");
}

renderWorkingCatalog();
localeSelect.addEventListener("change", () => renderWorkingCatalog(localeSelect.value));

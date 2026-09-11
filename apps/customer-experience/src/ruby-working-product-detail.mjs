import { workingCatalogPreview } from "./ruby-working-catalog-preview.mjs";

const copy = Object.freeze({
  en: Object.freeze({
    workingPreview: "Working preview",
    from: "From",
    both: "Pickup and delivery are present in the current working source.",
    pickup: "Pickup is present in the current working source.",
    delivery: "Delivery is present in the current working source.",
    neither: "Fulfillment eligibility is not confirmed in the current working source.",
    fallback: "Japanese product copy remains owner-gated. Approved English source copy is shown instead of inventing a translation.",
    fulfillmentCaution: "Final packaging, shipping, availability, and launch approval remain separate gates.",
  }),
  ja: Object.freeze({
    workingPreview: "作業中プレビュー",
    from: "〜",
    both: "現在の作業中ソースでは、店頭受取と配送の両方が設定されています。",
    pickup: "現在の作業中ソースでは、店頭受取が設定されています。",
    delivery: "現在の作業中ソースでは、配送が設定されています。",
    neither: "現在の作業中ソースでは、受取・配送条件は確定していません。",
    fallback: "日本語の商品コピーはオーナー承認待ちです。未承認の翻訳は作成せず、承認済みの英語原文を表示しています。",
    fulfillmentCaution: "最終梱包、配送、在庫状況、公開承認は別途確定が必要です。",
  }),
});

export function normalizeRubyLocale(value) {
  return value === "ja" ? "ja" : "en";
}

export function formatRubyYen(value) {
  if (!Number.isInteger(value) || value <= 0) throw new TypeError("positive integer JPY price required");
  return `¥${value.toLocaleString("en-US")}`;
}

export function findWorkingProduct(productKey) {
  if (typeof productKey !== "string" || !productKey.startsWith("RCD-")) return null;
  return workingCatalogPreview.products.find((product) => product.key === productKey) || null;
}

function fulfillmentKey(product) {
  if (product.pickup_allowed && product.delivery_allowed) return "both";
  if (product.pickup_allowed) return "pickup";
  if (product.delivery_allowed) return "delivery";
  return "neither";
}

export function workingProductDetailModel(productKey, locale = "en") {
  const product = findWorkingProduct(productKey);
  if (!product) return null;

  const lang = normalizeRubyLocale(locale);
  const localizedName = lang === "ja" ? product.japanese_name : product.english_name;
  const localizedDescription = lang === "ja" ? product.japanese_description : product.english_description;
  const usesEnglishFallback = lang === "ja" && (!localizedName || !localizedDescription);
  const price = product.price_mode === "from"
    ? lang === "ja" ? `${formatRubyYen(product.price_jpy)}${copy[lang].from}` : `${copy[lang].from} ${formatRubyYen(product.price_jpy)}`
    : formatRubyYen(product.price_jpy);

  return Object.freeze({
    key: product.key,
    name: localizedName || product.english_name,
    description: localizedDescription || product.english_description,
    price,
    productType: product.product_type,
    variants: Object.freeze(product.variants.map((variant) => Object.freeze({
      sizeCm: variant.size_cm,
      sku: variant.sku,
      price: formatRubyYen(variant.price_jpy),
    }))),
    fulfillment: copy[lang][fulfillmentKey(product)],
    fulfillmentCaution: copy[lang].fulfillmentCaution,
    workingPreviewLabel: copy[lang].workingPreview,
    usesEnglishFallback,
    fallbackMessage: usesEnglishFallback ? copy[lang].fallback : null,
    previewOnly: workingCatalogPreview.preview_only === true,
    catalogApproved: workingCatalogPreview.catalog_approved === true,
    mutationAuthorized: workingCatalogPreview.mutation_authorized === true,
    productionPublishAuthorized: workingCatalogPreview.production_publish_authorized === true,
  });
}

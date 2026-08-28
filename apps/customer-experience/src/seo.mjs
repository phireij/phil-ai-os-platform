import { localized, normalizeLocale, productStructuredData } from "./core.mjs";

export const SEO_MODES = Object.freeze(["preview", "deployment"]);

function normalizedBase(value) {
  if (typeof value !== "string" || !value.startsWith("https://")) {
    throw new TypeError("deployment canonical base must be explicit HTTPS");
  }
  return value.replace(/\/$/, "");
}

export function catalogMetadata(locale, mode = "preview", canonicalBase = null) {
  const lang = normalizeLocale(locale);
  const title = lang === "ja" ? "商品一覧 | カスタマーエクスペリエンス" : "Catalog | Customer Experience";
  const description = lang === "ja"
    ? "バイリンガル商品体験のカタログページです。"
    : "Bilingual customer-experience catalog page.";
  return Object.freeze({
    title,
    description,
    robots: mode === "deployment" ? "index,follow" : "noindex,nofollow",
    canonical: mode === "deployment" ? `${normalizedBase(canonicalBase)}/?lang=${lang}` : null,
  });
}

export function productMetadata(product, locale, mode = "preview", canonicalBase = null) {
  if (!SEO_MODES.includes(mode)) throw new TypeError("unsupported SEO mode");
  const lang = normalizeLocale(locale);
  const seo = product.seo || {};
  const title = seo.title ? localized(seo.title, lang) : localized(product.name, lang);
  const description = seo.description ? localized(seo.description, lang) : localized(product.description, lang);
  const base = mode === "deployment" ? normalizedBase(canonicalBase) : null;
  return Object.freeze({
    title,
    description,
    robots: mode === "deployment" ? "index,follow" : "noindex,nofollow",
    canonical: base ? `${base}/?product=${encodeURIComponent(product.product_key)}&lang=${lang}` : null,
    structuredData: productStructuredData(product, lang, base || "https://example.invalid"),
  });
}

import { localized, normalizeLocale, productStructuredData } from "./core.mjs";

export const SEO_MODES = Object.freeze(["preview", "deployment"]);

function normalizedBase(value) {
  if (typeof value !== "string" || !value.startsWith("https://")) {
    throw new TypeError("deployment canonical base must be explicit HTTPS");
  }
  return value.replace(/\/$/, "");
}

function localizedAlternates(base, pathBuilder) {
  return Object.freeze({
    en: pathBuilder(base, "en"),
    ja: pathBuilder(base, "ja"),
    "x-default": pathBuilder(base, "en"),
  });
}

export function catalogMetadata(locale, mode = "preview", canonicalBase = null) {
  if (!SEO_MODES.includes(mode)) throw new TypeError("unsupported SEO mode");
  const lang = normalizeLocale(locale);
  const title = lang === "ja" ? "商品一覧 | カスタマーエクスペリエンス" : "Catalog | Customer Experience";
  const description = lang === "ja"
    ? "バイリンガル商品体験のカタログページです。"
    : "Bilingual customer-experience catalog page.";
  const base = mode === "deployment" ? normalizedBase(canonicalBase) : null;
  return Object.freeze({
    title,
    description,
    robots: mode === "deployment" ? "index,follow" : "noindex,nofollow",
    canonical: base ? `${base}/?lang=${lang}` : null,
    alternates: base
      ? localizedAlternates(base, (root, alternateLang) => `${root}/?lang=${alternateLang}`)
      : null,
  });
}

export function productMetadata(product, locale, mode = "preview", canonicalBase = null) {
  if (!SEO_MODES.includes(mode)) throw new TypeError("unsupported SEO mode");
  const lang = normalizeLocale(locale);
  const seo = product.seo || {};
  const title = seo.title ? localized(seo.title, lang) : localized(product.name, lang);
  const description = seo.description ? localized(seo.description, lang) : localized(product.description, lang);
  const base = mode === "deployment" ? normalizedBase(canonicalBase) : null;
  const encodedProductKey = encodeURIComponent(product.product_key);
  return Object.freeze({
    title,
    description,
    robots: mode === "deployment" ? "index,follow" : "noindex,nofollow",
    canonical: base ? `${base}/?product=${encodedProductKey}&lang=${lang}` : null,
    alternates: base
      ? localizedAlternates(
          base,
          (root, alternateLang) => `${root}/?product=${encodedProductKey}&lang=${alternateLang}`,
        )
      : null,
    structuredData: productStructuredData(product, lang, base || "https://example.invalid"),
  });
}

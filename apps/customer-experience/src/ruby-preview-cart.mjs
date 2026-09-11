import { workingCatalogPreview } from "./ruby-working-catalog-preview.mjs";

export const RUBY_PREVIEW_CART_STORAGE_KEY = "ruby_preview_cart_v1";

function defaultStorage() {
  return globalThis.sessionStorage;
}

function sourceProduct(productKey) {
  if (typeof productKey !== "string" || !productKey.startsWith("RCD-")) return null;
  return workingCatalogPreview.products.find((product) => product.key === productKey) || null;
}

export function previewCatalogLine(productKey, variantSku = null) {
  const product = sourceProduct(productKey);
  if (!product) return null;

  if (product.product_type === "variable") {
    if (typeof variantSku !== "string") return null;
    const variant = product.variants.find((candidate) => candidate.sku === variantSku);
    if (!variant) return null;
    return Object.freeze({
      lineKey: `${product.key}:${variant.sku}`,
      productKey: product.key,
      sku: variant.sku,
      englishName: product.english_name,
      japaneseName: product.japanese_name,
      sizeCm: variant.size_cm,
      unitPriceJpy: variant.price_jpy,
    });
  }

  if (variantSku !== null && variantSku !== product.key) return null;
  return Object.freeze({
    lineKey: product.key,
    productKey: product.key,
    sku: product.key,
    englishName: product.english_name,
    japaneseName: product.japanese_name,
    sizeCm: null,
    unitPriceJpy: product.price_jpy,
  });
}

function parseStoredItems(storage) {
  let raw;
  try {
    raw = storage.getItem(RUBY_PREVIEW_CART_STORAGE_KEY);
  } catch {
    return [];
  }
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function normalizedStoredItems(storage) {
  const normalized = [];
  for (const item of parseStoredItems(storage)) {
    if (!item || !Number.isInteger(item.quantity) || item.quantity <= 0) continue;
    const line = previewCatalogLine(item.productKey, item.variantSku ?? null);
    if (!line || line.lineKey !== item.lineKey) continue;
    normalized.push({
      lineKey: line.lineKey,
      productKey: line.productKey,
      variantSku: line.productKey === line.sku ? null : line.sku,
      quantity: item.quantity,
    });
  }
  return normalized;
}

function writeStoredItems(storage, items) {
  storage.setItem(RUBY_PREVIEW_CART_STORAGE_KEY, JSON.stringify(items));
}

export function previewCartSummary(storage = defaultStorage()) {
  const items = normalizedStoredItems(storage);
  const lines = items.map((item) => {
    const source = previewCatalogLine(item.productKey, item.variantSku);
    return Object.freeze({
      ...source,
      quantity: item.quantity,
      lineTotalJpy: source.unitPriceJpy * item.quantity,
    });
  });
  return Object.freeze({
    lines: Object.freeze(lines),
    itemCount: lines.reduce((total, line) => total + line.quantity, 0),
    totalJpy: lines.reduce((total, line) => total + line.lineTotalJpy, 0),
    previewOnly: workingCatalogPreview.preview_only === true,
    catalogApproved: workingCatalogPreview.catalog_approved === true,
    mutationAuthorized: workingCatalogPreview.mutation_authorized === true,
    productionPublishAuthorized: workingCatalogPreview.production_publish_authorized === true,
  });
}

export function addPreviewCartItem({ productKey, variantSku = null, quantity = 1 }, storage = defaultStorage()) {
  if (!Number.isInteger(quantity) || quantity <= 0) throw new TypeError("positive integer quantity required");
  const line = previewCatalogLine(productKey, variantSku);
  if (!line) throw new TypeError("valid working-catalog product selection required");

  const items = normalizedStoredItems(storage);
  const current = items.find((item) => item.lineKey === line.lineKey);
  if (current) current.quantity += quantity;
  else items.push({
    lineKey: line.lineKey,
    productKey: line.productKey,
    variantSku: line.productKey === line.sku ? null : line.sku,
    quantity,
  });
  writeStoredItems(storage, items);
  return previewCartSummary(storage);
}

export function setPreviewCartQuantity(lineKey, quantity, storage = defaultStorage()) {
  if (typeof lineKey !== "string") throw new TypeError("line key required");
  if (!Number.isInteger(quantity) || quantity < 0) throw new TypeError("non-negative integer quantity required");
  const items = normalizedStoredItems(storage);
  const index = items.findIndex((item) => item.lineKey === lineKey);
  if (index === -1) return previewCartSummary(storage);
  if (quantity === 0) items.splice(index, 1);
  else items[index].quantity = quantity;
  writeStoredItems(storage, items);
  return previewCartSummary(storage);
}

export function removePreviewCartItem(lineKey, storage = defaultStorage()) {
  return setPreviewCartQuantity(lineKey, 0, storage);
}

export function clearPreviewCart(storage = defaultStorage()) {
  storage.removeItem(RUBY_PREVIEW_CART_STORAGE_KEY);
  return previewCartSummary(storage);
}

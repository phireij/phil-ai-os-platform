import test from "node:test";
import assert from "node:assert/strict";

import {
  addPreviewCartItem,
  clearPreviewCart,
  previewCatalogLine,
  previewCartSummary,
  removePreviewCartItem,
  setPreviewCartQuantity,
} from "../src/ruby-preview-cart.mjs";

class MemoryStorage {
  constructor() { this.data = new Map(); }
  getItem(key) { return this.data.has(key) ? this.data.get(key) : null; }
  setItem(key, value) { this.data.set(key, String(value)); }
  removeItem(key) { this.data.delete(key); }
}

test("cart resolves variable selections from the bounded working catalog", () => {
  const line = previewCatalogLine("RCD-MCH-RD", "RCD-MCH-RD-21");
  assert.ok(line);
  assert.equal(line.sizeCm, 21);
  assert.equal(line.unitPriceJpy, 5500);
  assert.equal(previewCatalogLine("RCD-MCH-RD", "RCD-MCH-RD-99"), null);
});

test("local cart stores only selections and rehydrates source-backed prices", () => {
  const storage = new MemoryStorage();
  addPreviewCartItem({ productKey: "RCD-BAR-FMB" }, storage);
  addPreviewCartItem({ productKey: "RCD-MCH-RD", variantSku: "RCD-MCH-RD-15", quantity: 2 }, storage);

  const summary = previewCartSummary(storage);
  assert.equal(summary.itemCount, 3);
  assert.equal(summary.totalJpy, 7250);
  assert.equal(summary.previewOnly, true);
  assert.equal(summary.catalogApproved, false);
  assert.equal(summary.mutationAuthorized, false);
  assert.equal(summary.productionPublishAuthorized, false);
});

test("quantity changes and removal remain local", () => {
  const storage = new MemoryStorage();
  let summary = addPreviewCartItem({ productKey: "RCD-BRD-ENS-1" }, storage);
  const lineKey = summary.lines[0].lineKey;
  summary = setPreviewCartQuantity(lineKey, 3, storage);
  assert.equal(summary.itemCount, 3);
  assert.equal(summary.totalJpy, 900);
  summary = removePreviewCartItem(lineKey, storage);
  assert.equal(summary.lines.length, 0);
});

test("tampered stored product facts cannot override the projection", () => {
  const storage = new MemoryStorage();
  storage.setItem("ruby_preview_cart_v1", JSON.stringify([
    { lineKey: "RCD-BAR-FMB", productKey: "RCD-BAR-FMB", variantSku: null, quantity: 2, unitPriceJpy: 1 },
    { lineKey: "RCD-FAKE", productKey: "RCD-FAKE", variantSku: null, quantity: 100 },
  ]));
  const summary = previewCartSummary(storage);
  assert.equal(summary.lines.length, 1);
  assert.equal(summary.totalJpy, 500);
});

test("clear and invalid quantities fail safely", () => {
  const storage = new MemoryStorage();
  addPreviewCartItem({ productKey: "RCD-BAR-FMB" }, storage);
  assert.equal(clearPreviewCart(storage).lines.length, 0);
  assert.throws(() => addPreviewCartItem({ productKey: "RCD-BAR-FMB", quantity: 0 }, storage));
  assert.throws(() => setPreviewCartQuantity("RCD-BAR-FMB", -1, storage));
});

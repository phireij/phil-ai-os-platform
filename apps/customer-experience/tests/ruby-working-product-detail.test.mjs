import test from "node:test";
import assert from "node:assert/strict";

import {
  findWorkingProduct,
  formatRubyYen,
  workingProductDetailModel,
} from "../src/ruby-working-product-detail.mjs";

test("working detail uses the bounded variable-product source facts", () => {
  const detail = workingProductDetailModel("RCD-MCH-RD", "en");
  assert.ok(detail);
  assert.equal(detail.name, "Moist Chocolate Round Cake");
  assert.equal(detail.price, "From ¥3,500");
  assert.deepEqual(
    detail.variants.map(({ sizeCm, sku, price }) => [sizeCm, sku, price]),
    [
      [15, "RCD-MCH-RD-15", "¥3,500"],
      [21, "RCD-MCH-RD-21", "¥5,500"],
    ],
  );
  assert.equal(detail.previewOnly, true);
  assert.equal(detail.catalogApproved, false);
  assert.equal(detail.mutationAuthorized, false);
  assert.equal(detail.productionPublishAuthorized, false);
});

test("Japanese detail falls back to approved English source copy without inventing product copy", () => {
  const detail = workingProductDetailModel("RCD-BAR-FMB", "ja");
  assert.ok(detail);
  assert.equal(detail.name, "Fudgy Milky Bar");
  assert.equal(detail.price, "¥250");
  assert.equal(detail.usesEnglishFallback, true);
  assert.match(detail.fallbackMessage, /オーナー承認待ち/);
});

test("unknown product keys fail closed", () => {
  assert.equal(findWorkingProduct("RCD-NOT-PRESENT"), null);
  assert.equal(workingProductDetailModel("RCD-NOT-PRESENT", "en"), null);
  assert.equal(workingProductDetailModel("not-a-ruby-key", "en"), null);
});

test("JPY formatter rejects unsafe prices", () => {
  assert.equal(formatRubyYen(300), "¥300");
  assert.throws(() => formatRubyYen(0), /positive integer/);
  assert.throws(() => formatRubyYen(3.5), /positive integer/);
});

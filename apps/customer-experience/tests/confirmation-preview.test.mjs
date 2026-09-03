import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import {
  buildFinalConfirmationViewModel,
  validateFinalConfirmationFixture,
} from "../src/confirmation-preview.mjs";

const fixturePath = fileURLToPath(new URL("../fixtures/final-confirmation.json", import.meta.url));
const safeFixture = JSON.parse(fs.readFileSync(fixturePath, "utf-8"));

function clone(overrides = {}) {
  return structuredClone(Object.assign(structuredClone(safeFixture), overrides));
}

test("isolated final confirmation fixture is GREEN and non-authorizing", () => {
  const result = validateFinalConfirmationFixture(safeFixture);
  assert.equal(result.valid, true);
  assert.equal(result.fixture_only, true);
  assert.equal(result.actual_final_confirmation_screen_reviewed, false);
  assert.equal(result.order_creation_authorized, false);
  assert.equal(result.mutation_authorized, false);
  assert.equal(result.payment_execution_authorized, false);
  assert.equal(result.production_publish_authorized, false);
  assert.equal(result.total_jpy, 6350);
  assert.equal(result.payment_method, "konbini");
});

test("non-fixture final confirmation data is rejected", () => {
  assert.throws(
    () => validateFinalConfirmationFixture(clone({ fixture_only: false })),
    /fixture_only preview_only/,
  );
});

test("isolated preview cannot claim actual WooCommerce final-screen acceptance", () => {
  assert.throws(
    () => validateFinalConfirmationFixture(clone({ actual_final_confirmation_screen_reviewed: true })),
    /cannot claim actual final-screen acceptance/,
  );
});

test("any order, mutation, payment or publication authority is rejected", () => {
  for (const key of ["order_creation_authorized", "mutation_authorized", "payment_execution_authorized", "production_publish_authorized"]) {
    assert.throws(
      () => validateFinalConfirmationFixture(clone({ [key]: true })),
      new RegExp(`${key} must remain false`),
    );
  }
});

test("inconsistent subtotal or total is rejected", () => {
  const badSubtotal = clone();
  badSubtotal.pricing.subtotal_jpy = 4999;
  assert.throws(() => validateFinalConfirmationFixture(badSubtotal), /subtotal does not match/);

  const badTotal = clone();
  badTotal.pricing.total_jpy = 9999;
  assert.throws(() => validateFinalConfirmationFixture(badTotal), /total does not match/);
});

test("current exempt tax posture cannot silently gain WooCommerce tax", () => {
  const taxEnabled = clone();
  taxEnabled.pricing.woocommerce_tax_enabled = true;
  assert.throws(() => validateFinalConfirmationFixture(taxEnabled), /must not add WooCommerce consumption tax/);

  const separateTax = clone();
  separateTax.pricing.separate_consumption_tax_jpy = 635;
  assert.throws(() => validateFinalConfirmationFixture(separateTax), /must not add WooCommerce consumption tax/);
});

test("Konbini expiry must preserve verified 3-day Live setting", () => {
  const changed = clone();
  changed.payment.expiry_days = 4;
  assert.throws(() => validateFinalConfirmationFixture(changed), /verified 3-day Live expiry/);
});

test("payment method outside approved initial subset is rejected", () => {
  const changed = clone();
  changed.payment.method = "bank_transfer";
  assert.throws(() => validateFinalConfirmationFixture(changed), /outside the approved initial subset/);
});

test("view model renders bilingual transaction terms without adding authority", () => {
  const en = buildFinalConfirmationViewModel(safeFixture, "en");
  const ja = buildFinalConfirmationViewModel(safeFixture, "ja");
  assert.equal(en.total, "¥6,350");
  assert.equal(ja.total, "￥6,350");
  assert.match(en.paymentDeadline, /transaction-specific KOMOJU deadline/);
  assert.match(ja.paymentDeadline, /KOMOJU/);
  assert.match(en.taxSummary, /consumption-tax exempt/);
  assert.match(ja.taxSummary, /消費税免税事業者/);
});

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8");
const index = readFileSync(new URL("../index.html", import.meta.url), "utf8");

test("mobile controls retain minimum touch targets and iOS-safe form sizing", () => {
  assert.match(styles, /min-height:\s*44px/);
  assert.match(styles, /@media \(max-width: 479px\)/);
  assert.match(styles, /font-size:\s*16px/);
  assert.match(styles, /\.primary-button\s*\{\s*width:\s*100%/);
});

test("small-screen product actions become full-width and readable", () => {
  assert.match(styles, /\.product-card-footer\s*\{[^}]*flex-direction:\s*column/s);
  assert.match(styles, /\.product-card-footer \.detail-link\s*\{\s*width:\s*100%/);
  assert.match(styles, /overflow-wrap:\s*anywhere/);
});

test("high contrast, forced colors, focus and reduced motion remain supported", () => {
  assert.match(styles, /@media \(prefers-contrast: more\)/);
  assert.match(styles, /@media \(forced-colors: active\)/);
  assert.match(styles, /summary:focus-visible/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});

test("document keeps mobile viewport and keyboard navigation landmarks", () => {
  assert.match(index, /viewport-fit=cover/);
  assert.match(index, /class="skip-link" href="#main"/);
  assert.match(index, /<main id="main" tabindex="-1">/);
  assert.match(index, /id="catalog-grid"[^>]*aria-live="polite"/);
});

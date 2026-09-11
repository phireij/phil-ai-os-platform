import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const storefrontSource = readFileSync(
  new URL("../src/ruby-storefront.mjs", import.meta.url),
  "utf8",
);

test("working-preview badge does not inherit product-initial span typography", () => {
  assert.match(storefrontSource, /const chip = document\.createElement\("div"\)/);
  assert.doesNotMatch(storefrontSource, /const chip = document\.createElement\("span"\)/);
});

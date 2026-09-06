import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sourceUrl = new URL("../src/order-intake-preview.mjs", import.meta.url);
const htmlUrl = new URL("../order-intake-preview.html", import.meta.url);

test("hidden custom-cake controls are disabled rather than remaining successful form controls", async () => {
  const source = await readFile(sourceUrl, "utf8");
  assert.match(source, /customFields\s*\.querySelectorAll\("input, select, textarea, button"\)/);
  assert.match(source, /control\.disabled = !custom/);
  assert.match(source, /referenceImages\.setCustomValidity\(""\)/);
});

test("custom-cake fields remain grouped under the hidden conditional container", async () => {
  const html = await readFile(htmlUrl, "utf8");
  assert.match(html, /<div id="custom-cake-fields" hidden>/);
  assert.match(html, /id="reference-images"/);
  assert.match(html, /name="photo-topper"/);
  assert.match(html, /name="edible-topper"/);
});

test("hidden Yamato time-window state is disabled outside Yamato fulfillment", async () => {
  const source = await readFile(sourceUrl, "utf8");
  assert.match(source, /yamatoWindowField\.hidden = !isYamato/);
  assert.match(source, /yamatoWindow\.disabled = !isYamato/);
});

test("requested-date language distinguishes pickup from delivery without changing the field contract", async () => {
  const source = await readFile(sourceUrl, "utf8");
  const html = await readFile(htmlUrl, "utf8");
  assert.match(source, /Requested delivery date \/ 希望配達日/);
  assert.match(source, /Requested pickup date \/ 希望受取日/);
  assert.match(source, /selectedFulfillment\(\) === "pickup" \? requestedDateCopy\.pickup : requestedDateCopy\.delivery/);
  assert.match(html, /id="requested-date-label"/);
  assert.match(html, /id="summary-date-label"/);
  assert.match(html, /id="requested-date" name="requested-date" type="date" required/);
});

test("page notice and preview success follow pickup versus delivery semantics", async () => {
  const source = await readFile(sourceUrl, "utf8");
  assert.match(source, /Your requested pickup date and time are not guaranteed yet/);
  assert.match(source, /Pickup availability and final quote still require confirmation before payment/);
  assert.match(source, /requestNotice\.textContent = dateCopy\.notice/);
  assert.match(source, /status\.textContent = fulfillmentDateCopy\(\)\.success/);
  assert.match(source, /Your requested delivery date and time are not guaranteed yet/);
});

test("order intake preview remains non-authorizing and network-inert", async () => {
  const source = await readFile(sourceUrl, "utf8");
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /XMLHttpRequest/);
  assert.doesNotMatch(source, /WebSocket/);
  assert.doesNotMatch(source, /sendBeacon/);
});

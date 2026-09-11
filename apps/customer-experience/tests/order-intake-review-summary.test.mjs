import assert from "node:assert/strict";
import test from "node:test";

import { orderIntakeReviewRows } from "../src/order-intake-review-summary.mjs";

test("custom requests expose reviewable notes, reference names, toppers, add-ons, and icing", () => {
  const rows = orderIntakeReviewRows({
    cakeType: "custom",
    customNotes: "Blue flowers and Happy Birthday",
    referenceImages: [
      { name: "front.jpg", type: "image/jpeg" },
      { name: "side.webp", type: "image/webp" },
    ],
    photoTopper: true,
    edibleTopper: true,
    addons: ["candles", "message-plaque"],
    icingRequested: true,
  });

  assert.deepEqual(rows, [
    { label: "Design notes / デザイン要望", value: "Blue flowers and Happy Birthday" },
    { label: "Reference images / 参考画像", value: "2: front.jpg, side.webp" },
    { label: "Topper / トッパー", value: "Photo / フォト, Edible / エディブル" },
    { label: "Add-ons / オプション", value: "Candles / キャンドル, Message plaque / メッセージプレート" },
    { label: "Icing / アイシング", value: "Requested / 希望あり" },
  ]);
});

test("basic requests suppress custom-only review rows", () => {
  const rows = orderIntakeReviewRows({
    cakeType: "basic",
    customNotes: "must stay hidden",
    referenceImages: [{ name: "private.jpg", type: "image/jpeg" }],
    photoTopper: true,
    addons: ["number-candle"],
    icingRequested: true,
  });

  assert.deepEqual(rows, [
    { label: "Add-ons / オプション", value: "Number candle / ナンバーキャンドル" },
    { label: "Icing / アイシング", value: "Requested / 希望あり" },
  ]);
});

test("empty selections add no redundant review rows", () => {
  assert.deepEqual(orderIntakeReviewRows({ cakeType: "basic" }), []);
});

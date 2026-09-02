import assert from "node:assert/strict";
import test from "node:test";

import { readinessFeedback } from "../src/readiness-feedback.mjs";

test("ready feedback stays non-authorizing", () => {
  const feedback = readinessFeedback(
    {
      ready: true,
      blockers: [],
      customer_action_required: [],
      mutation_authorized: false,
    },
    "en",
  );
  assert.equal(feedback.ready, true);
  assert.equal(feedback.summary, "Your selections are complete for this preview.");
  assert.equal(feedback.mutation_authorized, false);
});

test("pickup-time blocker is customer friendly in English", () => {
  const feedback = readinessFeedback(
    {
      ready: false,
      blockers: ["pickup_time"],
      customer_action_required: ["select_pickup_time"],
      mutation_authorized: false,
    },
    "en",
  );
  assert.deepEqual(feedback.blocker_messages, ["Choose a preferred pickup time to continue."]);
  assert.deepEqual(feedback.action_messages, ["Select a pickup date and time."]);
});

test("inventory blocker is customer friendly in Japanese", () => {
  const feedback = readinessFeedback(
    {
      ready: false,
      blockers: ["inventory"],
      customer_action_required: [],
      mutation_authorized: false,
    },
    "ja",
  );
  assert.equal(feedback.locale, "ja");
  assert.deepEqual(feedback.blocker_messages, ["チェックアウトを続ける前に、一部商品の在庫確認が必要です。"]);
});

test("duplicate blockers and actions are suppressed deterministically", () => {
  const feedback = readinessFeedback(
    {
      ready: false,
      blockers: ["pickup_time", "pickup_time"],
      customer_action_required: ["select_pickup_time", "select_pickup_time"],
      mutation_authorized: false,
    },
    "en",
  );
  assert.equal(feedback.blocker_messages.length, 1);
  assert.equal(feedback.action_messages.length, 1);
});

test("authorizing readiness input fails closed", () => {
  assert.throws(
    () => readinessFeedback({ ready: true, blockers: [], mutation_authorized: true }, "en"),
    /must remain non-authorizing/,
  );
});

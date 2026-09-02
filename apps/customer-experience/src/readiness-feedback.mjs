import { normalizeLocale } from "./core.mjs";

const messages = Object.freeze({
  en: Object.freeze({
    ready: "Your selections are complete for this preview.",
    pickup_time: "Choose a preferred pickup time to continue.",
    inventory: "One or more items need an availability review before checkout can continue.",
    select_pickup_time: "Select a pickup date and time.",
    unknown: (code) => `Additional review is required (${code}).`,
  }),
  ja: Object.freeze({
    ready: "このプレビューに必要な選択項目は揃っています。",
    pickup_time: "続行するには希望受取日時を選択してください。",
    inventory: "チェックアウトを続ける前に、一部商品の在庫確認が必要です。",
    select_pickup_time: "受取日時を選択してください。",
    unknown: (code) => `追加確認が必要です（${code}）。`,
  }),
});

export function readinessFeedback(readiness, locale) {
  if (!readiness || typeof readiness !== "object") {
    throw new TypeError("readiness is required");
  }
  if (readiness.mutation_authorized !== false) {
    throw new Error("readiness feedback must remain non-authorizing");
  }

  const selectedLocale = normalizeLocale(locale);
  const copy = messages[selectedLocale];
  const blockers = Array.isArray(readiness.blockers) ? [...new Set(readiness.blockers)] : [];
  const actions = Array.isArray(readiness.customer_action_required)
    ? [...new Set(readiness.customer_action_required)]
    : [];

  const blockerMessages = blockers.map((code) => copy[code] || copy.unknown(code));
  const actionMessages = actions.map((code) => copy[code] || copy.unknown(code));
  const ready = readiness.ready === true && blockers.length === 0;

  return Object.freeze({
    locale: selectedLocale,
    ready,
    summary: ready ? copy.ready : blockerMessages[0] || copy.unknown("review"),
    blocker_messages: Object.freeze(blockerMessages),
    action_messages: Object.freeze(actionMessages),
    mutation_authorized: false,
  });
}

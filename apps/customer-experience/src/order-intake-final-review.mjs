import { loadOrderIntakeReviewCarryover } from "./order-intake-review-continuity.mjs";
import { orderIntakeReviewRows } from "./order-intake-review-summary.mjs";

export function orderIntakeFinalReviewRows(storage) {
  const state = loadOrderIntakeReviewCarryover(storage);
  return state ? orderIntakeReviewRows(state) : [];
}

export function orderIntakeFinalReviewCorrectionHref(search = "") {
  const params = new URLSearchParams(search);
  return params.get("lang") === "ja"
    ? "./order-intake-preview.html?lang=ja"
    : "./order-intake-preview.html";
}

export function renderOrderIntakeFinalReview(
  root,
  storage = globalThis.sessionStorage,
  doc = globalThis.document,
  search = globalThis.location?.search || "",
) {
  if (!root || !doc) return false;
  const rows = orderIntakeFinalReviewRows(storage);
  if (!rows.length) {
    root.hidden = true;
    root.replaceChildren();
    return false;
  }

  root.hidden = false;
  const eyebrow = doc.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "Custom request review / オーダー内容確認";

  const heading = doc.createElement("h2");
  heading.textContent = "Confirm your custom request / オーダー内容をご確認ください";

  const note = doc.createElement("p");
  note.className = "checkout-reassurance";
  note.textContent = "Review-only context carried within this browser tab. Reference file contents are not stored, uploaded, or submitted. / このタブ内の確認用情報です。参考画像のファイル内容は保存・アップロード・送信されません。";

  const list = doc.createElement("dl");
  for (const row of rows) {
    const dt = doc.createElement("dt");
    const dd = doc.createElement("dd");
    dt.textContent = row.label;
    dd.textContent = row.value;
    list.append(dt, dd);
  }

  const correction = doc.createElement("p");
  const link = doc.createElement("a");
  link.className = "detail-link";
  link.href = orderIntakeFinalReviewCorrectionHref(search);
  link.textContent = "Edit custom request / オーダー内容を修正";
  correction.append(link);

  const correctionNote = doc.createElement("p");
  correctionNote.className = "field-help";
  correctionNote.textContent = "Text choices remain recoverable in this tab. Reference images must be selected again before review. / 入力内容はこのタブで復元できます。参考画像は確認前に再選択してください。";

  root.replaceChildren(eyebrow, heading, note, list, correction, correctionNote);
  return true;
}

export function installOrderIntakeFinalReview(
  doc = globalThis.document,
  storage = globalThis.sessionStorage,
  search = globalThis.location?.search || "",
) {
  if (!doc) return false;
  const root = doc.querySelector("#order-intake-final-review");
  if (!root) return false;
  return renderOrderIntakeFinalReview(root, storage, doc, search);
}

installOrderIntakeFinalReview();

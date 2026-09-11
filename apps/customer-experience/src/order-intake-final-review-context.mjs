import { loadOrderIntakeReviewCarryover } from "./order-intake-review-continuity.mjs";
import { orderIntakeCorrectionHref } from "./order-intake-cart-context.mjs";
import { orderIntakeReviewRows } from "./order-intake-review-summary.mjs";

export function orderIntakeFinalReviewRows(storage) {
  const state = loadOrderIntakeReviewCarryover(storage);
  return state ? orderIntakeReviewRows(state) : [];
}

export function renderOrderIntakeFinalReviewContext(
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
  eyebrow.textContent = "Order request / ご注文リクエスト";

  const heading = doc.createElement("h2");
  heading.textContent = "Custom request review / カスタム内容の最終確認";

  const note = doc.createElement("p");
  note.className = "checkout-reassurance";
  note.textContent = "Review-only context from this browser tab. Reference file contents are not stored, uploaded, or submitted. / このタブ内の確認情報です。参考画像のファイル内容は保存・アップロード・送信されません。";

  const list = doc.createElement("dl");
  for (const row of rows) {
    const dt = doc.createElement("dt");
    const dd = doc.createElement("dd");
    dt.textContent = row.label;
    dd.textContent = row.value;
    list.append(dt, dd);
  }

  const edit = doc.createElement("p");
  const editLink = doc.createElement("a");
  editLink.className = "text-link";
  editLink.href = orderIntakeCorrectionHref(search);
  editLink.textContent = "← Edit order request / ご注文リクエストを修正";
  edit.append(editLink);

  root.replaceChildren(eyebrow, heading, note, list, edit);
  return true;
}

export function installOrderIntakeFinalReviewContext(
  doc = globalThis.document,
  storage = globalThis.sessionStorage,
  search = globalThis.location?.search || "",
) {
  if (!doc) return false;
  const root = doc.querySelector("#order-intake-final-review-context");
  if (!root) return false;
  return renderOrderIntakeFinalReviewContext(root, storage, doc, search);
}

installOrderIntakeFinalReviewContext();

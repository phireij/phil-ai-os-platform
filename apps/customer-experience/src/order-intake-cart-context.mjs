import { loadOrderIntakeReviewCarryover } from "./order-intake-review-continuity.mjs";
import { orderIntakeReviewRows } from "./order-intake-review-summary.mjs";

export function orderIntakeCartContextRows(storage) {
  const state = loadOrderIntakeReviewCarryover(storage);
  return state ? orderIntakeReviewRows(state) : [];
}

export function orderIntakeCorrectionHref(search = "") {
  const params = new URLSearchParams(search);
  const lang = params.get("lang") === "ja" ? "ja" : null;
  return lang ? `./order-intake-preview.html?lang=${lang}` : "./order-intake-preview.html";
}

export function renderOrderIntakeCartContext(
  root,
  storage = globalThis.sessionStorage,
  doc = globalThis.document,
  search = globalThis.location?.search || "",
) {
  if (!root || !doc) return false;
  const rows = orderIntakeCartContextRows(storage);
  if (!rows.length) {
    root.hidden = true;
    root.replaceChildren();
    return false;
  }

  root.hidden = false;
  const heading = doc.createElement("h2");
  heading.textContent = "Custom request carried forward / オーダー内容の引き継ぎ";
  const note = doc.createElement("p");
  note.className = "checkout-reassurance";
  note.textContent = "Review-only continuity for this browser tab. Reference file contents are not stored or uploaded. / このタブ内の確認用引き継ぎです。参考画像のファイル内容は保存・送信されません。";
  const list = doc.createElement("dl");

  for (const row of rows) {
    const dt = doc.createElement("dt");
    const dd = doc.createElement("dd");
    dt.textContent = row.label;
    dd.textContent = row.value;
    list.append(dt, dd);
  }

  const correction = doc.createElement("p");
  const correctionLink = doc.createElement("a");
  correctionLink.className = "detail-link";
  correctionLink.href = orderIntakeCorrectionHref(search);
  correctionLink.textContent = "Edit order request / ご注文リクエストを修正";
  correction.append(correctionLink);

  const correctionNote = doc.createElement("p");
  correctionNote.className = "field-help";
  correctionNote.textContent = "Your text choices are restored in this tab. Reference images must be selected again before review. / 入力内容はこのタブで復元されます。参考画像は確認前に再選択してください。";

  root.replaceChildren(heading, note, list, correction, correctionNote);
  return true;
}

export function installOrderIntakeCartContext(
  doc = globalThis.document,
  storage = globalThis.sessionStorage,
  search = globalThis.location?.search || "",
) {
  if (!doc) return false;
  const root = doc.querySelector("#order-intake-cart-context");
  if (!root) return false;
  return renderOrderIntakeCartContext(root, storage, doc, search);
}

installOrderIntakeCartContext();

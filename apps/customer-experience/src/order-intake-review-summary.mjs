import { saveOrderIntakeReviewCarryover } from "./order-intake-review-continuity.mjs";
import { buildOrderIntakeReviewState } from "./order-intake-review-state.mjs";

const ADDON_LABELS = {
  candles: "Candles / キャンドル",
  "number-candle": "Number candle / ナンバーキャンドル",
  "message-plaque": "Message plaque / メッセージプレート",
};

export function orderIntakeReviewRows(input = {}) {
  const state = buildOrderIntakeReviewState(input);
  const rows = [];

  if (state.cakeType === "custom") {
    rows.push({ label: "Design notes / デザイン要望", value: state.customNotes || "Not provided / 未入力" });
    rows.push({
      label: "Reference images / 参考画像",
      value: state.referenceImageCount
        ? `${state.referenceImageCount}: ${state.referenceImages.map((item) => item.name).join(", ")}`
        : "None selected / 未選択",
    });
    const toppers = [];
    if (state.photoTopper) toppers.push("Photo / フォト");
    if (state.edibleTopper) toppers.push("Edible / エディブル");
    rows.push({ label: "Topper / トッパー", value: toppers.join(", ") || "None / なし" });
  }

  if (state.addons.length) {
    rows.push({
      label: "Add-ons / オプション",
      value: state.addons.map((item) => ADDON_LABELS[item]).join(", "),
    });
  }

  if (state.icingRequested) {
    rows.push({ label: "Icing / アイシング", value: "Requested / 希望あり" });
  }

  return Object.freeze(rows.map((row) => Object.freeze(row)));
}

export function currentOrderIntakeReviewInput(form) {
  const cakeType = form.querySelector("#cake-type");
  const notes = form.querySelector("#custom-notes");
  const referenceImages = form.querySelector("#reference-images");
  return {
    cakeType: cakeType?.value,
    customNotes: notes?.value,
    referenceImages: Array.from(referenceImages?.files || []).map((file) => ({ name: file.name, type: file.type })),
    photoTopper: Boolean(form.querySelector('input[name="photo-topper"]')?.checked),
    edibleTopper: Boolean(form.querySelector('input[name="edible-topper"]')?.checked),
    addons: Array.from(form.querySelectorAll('input[name="addon"]:checked')).map((input) => input.value),
    icingRequested: Boolean(form.querySelector("#icing-requested")?.checked),
  };
}

export function renderOrderIntakeReviewSummary(form, summaryList, doc = globalThis.document, storage = globalThis.sessionStorage) {
  if (!form || !summaryList || !doc) return;
  const input = currentOrderIntakeReviewInput(form);
  saveOrderIntakeReviewCarryover(storage, input);
  summaryList.querySelectorAll('[data-order-intake-review="true"]').forEach((node) => node.remove());

  for (const row of orderIntakeReviewRows(input)) {
    const dt = doc.createElement("dt");
    const dd = doc.createElement("dd");
    dt.dataset.orderIntakeReview = "true";
    dd.dataset.orderIntakeReview = "true";
    dt.textContent = row.label;
    dd.textContent = row.value;
    summaryList.append(dt, dd);
  }
}

export function installOrderIntakeReviewSummary(doc = globalThis.document, storage = globalThis.sessionStorage) {
  if (!doc) return false;
  const form = doc.querySelector("#order-intake-form");
  const summaryList = doc.querySelector(".intake-summary dl");
  if (!form || !summaryList) return false;

  const render = () => renderOrderIntakeReviewSummary(form, summaryList, doc, storage);
  form.addEventListener("change", render);
  form.addEventListener("input", (event) => {
    if (event.target?.id !== "reference-images") render();
  });
  queueMicrotask(render);
  return true;
}

installOrderIntakeReviewSummary();

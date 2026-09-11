import { buildOrderIntakeReviewState } from "./order-intake-review-state.mjs";

export const ORDER_INTAKE_REVIEW_KEY = "rubys-order-intake-review-v1";
export const ORDER_INTAKE_REVIEW_VERSION = 1;

export function sanitizeOrderIntakeReviewCarryover(input = {}) {
  const state = buildOrderIntakeReviewState(input);
  return Object.freeze({
    version: ORDER_INTAKE_REVIEW_VERSION,
    cakeType: state.cakeType,
    customNotes: state.customNotes,
    referenceImages: state.referenceImages.map((item) => ({ name: item.name, type: item.type })),
    referenceImageCount: state.referenceImageCount,
    photoTopper: state.photoTopper,
    edibleTopper: state.edibleTopper,
    addons: [...state.addons],
    icingRequested: state.icingRequested,
    fileContentPersisted: false,
    networkCallPerformed: false,
    orderCreationAuthorized: false,
    paymentExecutionAuthorized: false,
  });
}

export function saveOrderIntakeReviewCarryover(storage, input) {
  if (!storage) return false;
  const safe = sanitizeOrderIntakeReviewCarryover(input);
  try {
    storage.setItem(ORDER_INTAKE_REVIEW_KEY, JSON.stringify(safe));
    return true;
  } catch {
    return false;
  }
}

export function loadOrderIntakeReviewCarryover(storage) {
  if (!storage) return null;
  try {
    const raw = storage.getItem(ORDER_INTAKE_REVIEW_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed?.version !== ORDER_INTAKE_REVIEW_VERSION) return null;
    return sanitizeOrderIntakeReviewCarryover(parsed);
  } catch {
    return null;
  }
}

export function clearOrderIntakeReviewCarryover(storage) {
  if (!storage) return false;
  try {
    storage.removeItem(ORDER_INTAKE_REVIEW_KEY);
    return true;
  } catch {
    return false;
  }
}

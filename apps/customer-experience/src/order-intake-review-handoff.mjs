import { buildOrderIntakeRequestEnvelope } from "./order-intake-request-envelope.mjs";

export const ORDER_INTAKE_REVIEW_HANDOFF_KEY = "rubys-order-intake-review-handoff-v1";
export const ORDER_INTAKE_REVIEW_HANDOFF_VERSION = 1;

export function buildOrderIntakeReviewHandoff(input = {}) {
  const request = buildOrderIntakeRequestEnvelope(input);
  return Object.freeze({
    schema: "rubys-order-intake-review-handoff",
    version: ORDER_INTAKE_REVIEW_HANDOFF_VERSION,
    state: "prepared_for_staff_review",
    request,
    authority: Object.freeze({
      staffReviewOnly: true,
      fileContentPersisted: false,
      fileUploadPerformed: false,
      networkCallPerformed: false,
      wooCommerceMutationAuthorized: false,
      orderCreationAuthorized: false,
      paymentExecutionAuthorized: false,
      smsSendAuthorized: false,
      inventoryMutationAuthorized: false,
      productionPublishAuthorized: false,
    }),
  });
}

export function saveOrderIntakeReviewHandoff(storage, input = {}) {
  if (!storage) return false;
  const handoff = buildOrderIntakeReviewHandoff(input);
  try {
    storage.setItem(ORDER_INTAKE_REVIEW_HANDOFF_KEY, JSON.stringify(handoff));
    return true;
  } catch {
    return false;
  }
}

export function loadOrderIntakeReviewHandoff(storage) {
  if (!storage) return null;
  try {
    const raw = storage.getItem(ORDER_INTAKE_REVIEW_HANDOFF_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (
      parsed?.schema !== "rubys-order-intake-review-handoff" ||
      parsed?.version !== ORDER_INTAKE_REVIEW_HANDOFF_VERSION ||
      parsed?.state !== "prepared_for_staff_review"
    ) return null;
    return buildOrderIntakeReviewHandoff({
      ...parsed.request?.fulfillment,
      ...parsed.request?.customization,
      fulfillment: parsed.request?.fulfillment?.method,
    });
  } catch {
    return null;
  }
}

export function clearOrderIntakeReviewHandoff(storage) {
  if (!storage) return false;
  try {
    storage.removeItem(ORDER_INTAKE_REVIEW_HANDOFF_KEY);
    return true;
  } catch {
    return false;
  }
}

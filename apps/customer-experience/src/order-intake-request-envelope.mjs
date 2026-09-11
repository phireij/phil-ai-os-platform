import { sanitizeOrderIntakeDraft } from "./order-intake-draft-state.mjs";
import { buildOrderIntakeReviewState } from "./order-intake-review-state.mjs";

export const ORDER_INTAKE_REQUEST_ENVELOPE_VERSION = 1;

function safeDraft(input = {}) {
  return sanitizeOrderIntakeDraft({
    ...input,
    version: 1,
  }) || sanitizeOrderIntakeDraft({ version: 1 });
}

export function buildOrderIntakeRequestEnvelope(input = {}) {
  const draft = safeDraft(input);
  const review = buildOrderIntakeReviewState(input);

  const fulfillment = Object.freeze({
    method: draft.fulfillment,
    requestedDate: draft.requestedDate,
    pickupTime: draft.fulfillment === "pickup" ? draft.pickupTime : "",
    yamatoWindow: draft.fulfillment === "yamato" ? draft.yamatoWindow : "none",
    routeOrFeeConfirmed: false,
    fulfillmentConfirmed: false,
  });

  const customization = Object.freeze({
    cakeType: review.cakeType,
    customNotes: review.customNotes,
    referenceImages: Object.freeze(review.referenceImages.map((item) => Object.freeze({
      name: item.name,
      type: item.type,
    }))),
    referenceImageCount: review.referenceImageCount,
    photoTopper: review.photoTopper,
    edibleTopper: review.edibleTopper,
    addons: Object.freeze([...review.addons]),
    icingRequested: review.icingRequested,
  });

  return Object.freeze({
    schema: "rubys-order-intake-request",
    version: ORDER_INTAKE_REQUEST_ENVELOPE_VERSION,
    state: "review_only",
    fulfillment,
    customization,
    pricing: Object.freeze({
      quoteCalculated: false,
      shippingFeeCalculated: false,
      totalCalculated: false,
    }),
    authority: Object.freeze({
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

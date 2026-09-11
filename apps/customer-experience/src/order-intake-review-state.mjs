const ALLOWED_ADDONS = new Set(["candles", "number-candle", "message-plaque"]);
const MAX_NOTES_LENGTH = 4000;
const MAX_REFERENCE_IMAGES = 8;
const MAX_REFERENCE_NAME_LENGTH = 160;

function boundedText(value, maxLength) {
  return typeof value === "string" ? value.slice(0, maxLength) : "";
}

export function buildOrderIntakeReviewState(input = {}) {
  const cakeType = input.cakeType === "custom" ? "custom" : "basic";
  const custom = cakeType === "custom";

  const referenceImages = custom && Array.isArray(input.referenceImages)
    ? input.referenceImages
        .slice(0, MAX_REFERENCE_IMAGES)
        .map((item) => ({
          name: boundedText(item?.name, MAX_REFERENCE_NAME_LENGTH),
          type: boundedText(item?.type, 80),
        }))
        .filter((item) => item.name)
    : [];

  const addons = Array.isArray(input.addons)
    ? [...new Set(input.addons.filter((item) => ALLOWED_ADDONS.has(item)))]
    : [];

  return Object.freeze({
    cakeType,
    customNotes: custom ? boundedText(input.customNotes, MAX_NOTES_LENGTH) : "",
    referenceImages: Object.freeze(referenceImages.map((item) => Object.freeze(item))),
    referenceImageCount: referenceImages.length,
    photoTopper: custom && input.photoTopper === true,
    edibleTopper: custom && input.edibleTopper === true,
    addons: Object.freeze(addons),
    icingRequested: input.icingRequested === true,
    fileContentPersisted: false,
    networkCallPerformed: false,
    orderCreationAuthorized: false,
    paymentExecutionAuthorized: false,
  });
}

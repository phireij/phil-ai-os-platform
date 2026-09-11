export const ORDER_INTAKE_DRAFT_KEY = "rubys-order-intake-preview-v1";
export const ORDER_INTAKE_DRAFT_VERSION = 1;

const FULFILLMENT = new Set(["yamato", "ruby-car", "pickup"]);
const CAKE_TYPES = new Set(["basic", "custom"]);
const YAMATO_WINDOWS = new Set(["none", "08-12", "14-16", "16-18", "18-20", "19-21"]);
const ADDONS = new Set(["candles", "number-candle", "message-plaque"]);

function text(value, maxLength) {
  return typeof value === "string" ? value.slice(0, maxLength) : "";
}

export function sanitizeOrderIntakeDraft(value) {
  if (!value || typeof value !== "object" || value.version !== ORDER_INTAKE_DRAFT_VERSION) {
    return null;
  }

  const fulfillment = FULFILLMENT.has(value.fulfillment) ? value.fulfillment : "yamato";
  const cakeType = CAKE_TYPES.has(value.cakeType) ? value.cakeType : "basic";
  const yamatoWindow = YAMATO_WINDOWS.has(value.yamatoWindow) ? value.yamatoWindow : "none";
  const addons = Array.isArray(value.addons)
    ? [...new Set(value.addons.filter((item) => ADDONS.has(item)))]
    : [];

  return {
    version: ORDER_INTAKE_DRAFT_VERSION,
    fulfillment,
    requestedDate: text(value.requestedDate, 10),
    pickupTime: text(value.pickupTime, 5),
    yamatoWindow,
    cakeType,
    customNotes: text(value.customNotes, 4000),
    photoTopper: value.photoTopper === true,
    edibleTopper: value.edibleTopper === true,
    addons,
    icingRequested: value.icingRequested === true,
  };
}

export function loadOrderIntakeDraft(storage) {
  if (!storage) return null;
  try {
    const raw = storage.getItem(ORDER_INTAKE_DRAFT_KEY);
    if (!raw) return null;
    return sanitizeOrderIntakeDraft(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function saveOrderIntakeDraft(storage, draft) {
  if (!storage) return false;
  const safe = sanitizeOrderIntakeDraft({
    ...draft,
    version: ORDER_INTAKE_DRAFT_VERSION,
  });
  if (!safe) return false;
  try {
    storage.setItem(ORDER_INTAKE_DRAFT_KEY, JSON.stringify(safe));
    return true;
  } catch {
    return false;
  }
}

export function clearOrderIntakeDraft(storage) {
  if (!storage) return false;
  try {
    storage.removeItem(ORDER_INTAKE_DRAFT_KEY);
    return true;
  } catch {
    return false;
  }
}

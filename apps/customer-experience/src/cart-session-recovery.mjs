const STORAGE_KEY = "phil-ai-os:cx:cart-session:v1";
const MAX_QUANTITY = 99;

function clampQuantity(value) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed)) return 0;
  return Math.min(MAX_QUANTITY, Math.max(0, parsed));
}

function safeSessionStorage() {
  try {
    const storage = window.sessionStorage;
    const probe = `${STORAGE_KEY}:probe`;
    storage.setItem(probe, "1");
    storage.removeItem(probe);
    return storage;
  } catch {
    return null;
  }
}

function snapshot() {
  const quantities = {};
  document.querySelectorAll("#cart-items [data-cart-sku]").forEach((input) => {
    if (!input.disabled && input.dataset.cartSku) quantities[input.dataset.cartSku] = clampQuantity(input.value);
  });
  return Object.freeze({
    version: 1,
    quantities,
    fulfillment: Object.freeze({
      mode: document.querySelector('input[name="fulfillment-mode"]:checked')?.value === "delivery" ? "delivery" : "pickup",
      pickupAt: document.querySelector("#pickup-at")?.value || "",
      deliveryArea: ["kanto", "other"].includes(document.querySelector("#delivery-area")?.value)
        ? document.querySelector("#delivery-area").value
        : "",
    }),
  });
}

function persist() {
  const storage = safeSessionStorage();
  if (!storage) return;
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(snapshot()));
  } catch {
    // Session recovery is optional; checkout must remain usable when storage is unavailable.
  }
}

function readSnapshot() {
  const storage = safeSessionStorage();
  if (!storage) return null;
  try {
    const parsed = JSON.parse(storage.getItem(STORAGE_KEY) || "null");
    if (!parsed || parsed.version !== 1 || typeof parsed.quantities !== "object" || !parsed.fulfillment) return null;
    return parsed;
  } catch {
    storage.removeItem(STORAGE_KEY);
    return null;
  }
}

function explicitProductSelectionPresent() {
  return Boolean(new URLSearchParams(location.search).get("product"));
}

function restore(saved) {
  if (!saved || explicitProductSelectionPresent()) return false;
  const inputs = [...document.querySelectorAll("#cart-items [data-cart-sku]")];
  const fulfillmentReady = Boolean(document.querySelector("#fulfillment-choice"));
  if (!inputs.length || !fulfillmentReady) return false;

  inputs.forEach((input) => {
    const savedValue = saved.quantities?.[input.dataset.cartSku];
    if (!input.disabled && Number.isInteger(Number(savedValue))) input.value = String(clampQuantity(savedValue));
  });

  const mode = saved.fulfillment.mode === "delivery" ? "delivery" : "pickup";
  const radio = document.querySelector(`input[name="fulfillment-mode"][value="${mode}"]`);
  if (radio) {
    radio.checked = true;
    radio.dispatchEvent(new Event("change", { bubbles: true }));
  }

  const pickupAt = document.querySelector("#pickup-at");
  if (pickupAt && typeof saved.fulfillment.pickupAt === "string") pickupAt.value = saved.fulfillment.pickupAt;

  const deliveryArea = document.querySelector("#delivery-area");
  if (deliveryArea && ["", "kanto", "other"].includes(saved.fulfillment.deliveryArea)) {
    deliveryArea.value = saved.fulfillment.deliveryArea;
    deliveryArea.dispatchEvent(new Event("change", { bubbles: true }));
  }

  const form = document.querySelector("#cart-form");
  form?.dispatchEvent(new Event("input", { bubbles: true }));
  form?.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

const saved = readSnapshot();
let restored = false;
function attemptRestore() {
  if (restored || !saved) return;
  restored = restore(saved);
  if (restored) observer.disconnect();
}

const observer = new MutationObserver(() => queueMicrotask(attemptRestore));
observer.observe(document.body, { childList: true, subtree: true });
queueMicrotask(attemptRestore);

const form = document.querySelector("#cart-form");
form?.addEventListener("input", () => queueMicrotask(persist));
form?.addEventListener("change", () => queueMicrotask(persist));
addEventListener("pagehide", persist);

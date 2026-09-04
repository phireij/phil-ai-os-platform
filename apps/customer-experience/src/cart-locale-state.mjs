function snapshotQuantities() {
  const values = new Map();
  document.querySelectorAll("#cart-items [data-cart-sku]").forEach((input) => {
    const quantity = Number(input.value);
    if (Number.isInteger(quantity) && quantity >= 0) values.set(input.dataset.cartSku, quantity);
  });
  return values;
}

function restoreQuantities(values) {
  if (!(values instanceof Map) || values.size === 0) return;
  document.querySelectorAll("#cart-items [data-cart-sku]").forEach((input) => {
    if (!input.disabled && values.has(input.dataset.cartSku)) {
      input.value = String(values.get(input.dataset.cartSku));
    }
  });
}

function snapshotFulfillment() {
  return Object.freeze({
    mode: document.querySelector('input[name="fulfillment-mode"]:checked')?.value || "pickup",
    pickupAt: document.querySelector("#pickup-at")?.value || "",
    deliveryArea: document.querySelector("#delivery-area")?.value || "",
  });
}

function restoreFulfillment(snapshot) {
  if (!snapshot || typeof snapshot !== "object") return;
  const mode = snapshot.mode === "delivery" ? "delivery" : "pickup";
  const radio = document.querySelector(`input[name="fulfillment-mode"][value="${mode}"]`);
  if (radio) {
    radio.checked = true;
    radio.dispatchEvent(new Event("change", { bubbles: true }));
  }
  const pickupAt = document.querySelector("#pickup-at");
  if (pickupAt) pickupAt.value = snapshot.pickupAt || "";
  const deliveryArea = document.querySelector("#delivery-area");
  if (deliveryArea) {
    deliveryArea.value = snapshot.deliveryArea || "";
    deliveryArea.dispatchEvent(new Event("change", { bubbles: true }));
  }
}

function restoreCartState(snapshot) {
  restoreQuantities(snapshot?.quantities);
  restoreFulfillment(snapshot?.fulfillment);
  document.querySelector("#cart-form")?.dispatchEvent(new Event("input", { bubbles: true }));
  document.querySelector("#cart-form")?.dispatchEvent(new Event("change", { bubbles: true }));
}

const localeSelect = document.querySelector("#locale-select");
localeSelect?.addEventListener("change", () => {
  const snapshot = Object.freeze({
    quantities: snapshotQuantities(),
    fulfillment: snapshotFulfillment(),
  });
  queueMicrotask(() => restoreCartState(snapshot));
}, true);

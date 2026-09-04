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
  document.querySelector("#cart-form")?.dispatchEvent(new Event("input", { bubbles: true }));
}

const localeSelect = document.querySelector("#locale-select");
localeSelect?.addEventListener("change", () => {
  const quantities = snapshotQuantities();
  queueMicrotask(() => restoreQuantities(quantities));
}, true);

const copy = {
  en: {
    label: "Cart",
    aria: (count) => count === 1 ? "Cart, 1 item selected" : `Cart, ${count} items selected`,
  },
  ja: {
    label: "カート",
    aria: (count) => `カート、${count}点選択中`,
  },
};

function locale() {
  return document.documentElement.lang === "ja" ? "ja" : "en";
}

export function selectedItemCount(root = document) {
  return [...root.querySelectorAll("#cart-items [data-cart-sku]")].reduce((total, input) => {
    if (input.disabled) return total;
    const quantity = Number(input.value);
    return Number.isInteger(quantity) && quantity > 0 ? total + quantity : total;
  }, 0);
}

export function updateCartDockStatus(root = document) {
  const label = root.querySelector("#dock-cart-label");
  const link = label?.closest("a");
  if (!label || !link) return;

  const lang = locale();
  const count = selectedItemCount(root);
  label.textContent = count > 0 ? `${copy[lang].label} (${count})` : copy[lang].label;
  link.setAttribute("aria-label", copy[lang].aria(count));
  link.dataset.cartCount = String(count);
}

const form = document.querySelector("#cart-form");
form?.addEventListener("input", () => queueMicrotask(() => updateCartDockStatus()));
form?.addEventListener("change", () => queueMicrotask(() => updateCartDockStatus()));
document.querySelector("#locale-select")?.addEventListener("change", () => queueMicrotask(() => updateCartDockStatus()));

const cartItems = document.querySelector("#cart-items");
if (cartItems) {
  new MutationObserver(() => queueMicrotask(() => updateCartDockStatus())).observe(cartItems, { childList: true, subtree: true });
}

updateCartDockStatus();

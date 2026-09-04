const requestedProductKey = new URLSearchParams(location.search).get("product");
let catalog = [];
let explicitSelectionApplied = false;

function localizedUnavailable() {
  return document.documentElement.lang === "ja"
    ? "選択した商品は現在カートで利用できません。"
    : "The selected product is not currently available in the cart.";
}

function applyExplicitSelection() {
  if (explicitSelectionApplied || !requestedProductKey) return;
  const inputs = [...document.querySelectorAll("#cart-items [data-cart-sku]")];
  if (!inputs.length || !catalog.length) return;

  explicitSelectionApplied = true;
  for (const input of inputs) input.value = "0";
  let matched = false;
  const requested = catalog.find((item) => item.product_key === requestedProductKey);
  const input = requested
    ? document.querySelector(`#cart-items [data-cart-sku="${CSS.escape(requested.sku)}"]`)
    : null;
  if (input && !input.disabled) {
    input.value = "1";
    matched = true;
  }

  document.querySelector("#cart-form")?.dispatchEvent(new Event("input", { bubbles: true }));
  document.querySelector("#cart-selection-notice")?.remove();
  if (!matched) {
    const summary = document.querySelector("#cart-summary");
    if (summary) {
      const message = document.createElement("span");
      message.id = "cart-selection-notice";
      message.className = "cart-selection-notice";
      message.setAttribute("role", "status");
      message.textContent = localizedUnavailable();
      summary.after(message);
    }
  }
}

async function bootSelectionContinuity() {
  if (!requestedProductKey) return;
  const response = await fetch("./fixtures/catalog.json", { cache: "no-store" });
  if (!response.ok) return;
  const payload = await response.json();
  if (payload.fixture_only !== true || !Array.isArray(payload.products)) return;
  catalog = payload.products;
  applyExplicitSelection();
}

const cartItems = document.querySelector("#cart-items");
if (cartItems) new MutationObserver(() => queueMicrotask(applyExplicitSelection)).observe(cartItems, { childList: true });
bootSelectionContinuity().catch(() => undefined);

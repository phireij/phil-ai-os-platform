const requestedProductKey = new URLSearchParams(location.search).get("product");

function applyExplicitSelection() {
  const inputs = [...document.querySelectorAll("#cart-items [data-cart-sku]")];
  if (!inputs.length) return;

  const cards = [...document.querySelectorAll("#cart-items .product-card")];
  let matched = false;
  for (const input of inputs) input.value = "0";

  if (requestedProductKey) {
    for (const card of cards) {
      const heading = card.querySelector("h3");
      const input = card.querySelector("[data-cart-sku]");
      if (!heading || !input || input.disabled) continue;
      const product = window.__cxCatalogProductKeys?.find((item) => item.sku === input.dataset.cartSku);
      if (product?.product_key === requestedProductKey) {
        input.value = "1";
        matched = true;
        break;
      }
    }
  }

  document.querySelector("#cart-form")?.dispatchEvent(new Event("input", { bubbles: true }));
  const notice = document.querySelector("#cart-selection-notice");
  if (notice) notice.remove();
  if (requestedProductKey && !matched) {
    const summary = document.querySelector("#cart-summary");
    if (summary) {
      const message = document.createElement("span");
      message.id = "cart-selection-notice";
      message.textContent = document.documentElement.lang === "ja" ? "選択した商品は現在カートで利用できません。" : "The selected product is not currently available in the cart.";
      summary.after(message);
    }
  }
}

const cartItems = document.querySelector("#cart-items");
if (cartItems) new MutationObserver(() => queueMicrotask(applyExplicitSelection)).observe(cartItems, { childList: true });

addEventListener("cx:catalog-ready", applyExplicitSelection);

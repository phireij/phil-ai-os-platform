const copy = {
  en: {
    decrease: (name) => `Decrease quantity — ${name}`,
    increase: (name) => `Increase quantity — ${name}`,
    quantity: (name) => `${name} quantity`,
    lineTotal: "Item total",
  },
  ja: {
    decrease: (name) => `${name}の数量を減らす`,
    increase: (name) => `${name}の数量を増やす`,
    quantity: (name) => `${name}の数量`,
    lineTotal: "商品小計",
  },
};

function locale() {
  return document.documentElement.lang === "ja" ? "ja" : "en";
}

function numericUnitPrice(text) {
  const normalized = String(text || "").replace(/[^0-9.-]/g, "");
  const value = Number(normalized);
  return Number.isFinite(value) && value >= 0 ? value : 0;
}

function formatYen(amount, lang = locale()) {
  return new Intl.NumberFormat(lang === "ja" ? "ja-JP" : "en-US", {
    style: "currency",
    currency: "JPY",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function clampQuantity(value, min = 0, max = 99) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed)) return min;
  return Math.min(max, Math.max(min, parsed));
}

function productNameForCard(card) {
  return card?.querySelector("h3")?.textContent?.trim() || "Product";
}

function accessibleToken(input) {
  const raw = input?.dataset?.cartSku || "item";
  return String(raw).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "item";
}

function connectCartItemSemantics(card, input, unitPrice, total) {
  const heading = card.querySelector("h3");
  if (!heading) return;
  const token = accessibleToken(input);
  heading.id ||= `cart-item-${token}-name`;
  unitPrice.id ||= `cart-item-${token}-unit-price`;
  total.id ||= `cart-item-${token}-line-total`;
  card.setAttribute("aria-labelledby", heading.id);
  card.setAttribute("aria-describedby", `${unitPrice.id} ${total.id}`);
  input.setAttribute("aria-describedby", `${unitPrice.id} ${total.id}`);
}

export function enhanceCartCard(card) {
  const input = card?.querySelector("[data-cart-sku]");
  const unitPrice = card?.querySelector(".price");
  if (!input || !unitPrice || input.disabled || card.querySelector(".quantity-stepper")) return;

  input.max = input.max || "99";
  const wrapper = document.createElement("div");
  wrapper.className = "quantity-stepper";
  wrapper.innerHTML = `<button type="button" class="quantity-step" data-delta="-1" aria-label=""></button><span class="quantity-input-slot"></span><button type="button" class="quantity-step" data-delta="1" aria-label=""></button>`;
  input.parentNode.insertBefore(wrapper, input);
  wrapper.querySelector(".quantity-input-slot").append(input);

  const total = document.createElement("p");
  total.className = "line-total";
  total.setAttribute("aria-live", "polite");
  total.setAttribute("aria-atomic", "true");
  card.querySelector(".product-card-body")?.append(total);
  connectCartItemSemantics(card, input, unitPrice, total);

  const update = () => {
    const lang = locale();
    const productName = productNameForCard(card);
    const quantity = clampQuantity(input.value, Number(input.min || 0), Number(input.max || 99));
    input.value = String(quantity);
    input.setAttribute("aria-label", copy[lang].quantity(productName));
    total.textContent = `${copy[lang].lineTotal}: ${formatYen(numericUnitPrice(unitPrice.textContent) * quantity, lang)}`;
    const [minus, plus] = wrapper.querySelectorAll(".quantity-step");
    minus.textContent = "−";
    plus.textContent = "+";
    minus.setAttribute("aria-label", copy[lang].decrease(productName));
    plus.setAttribute("aria-label", copy[lang].increase(productName));
    minus.setAttribute("aria-describedby", `${unitPrice.id} ${total.id}`);
    plus.setAttribute("aria-describedby", `${unitPrice.id} ${total.id}`);
    minus.disabled = quantity <= Number(input.min || 0);
    plus.disabled = quantity >= Number(input.max || 99);
  };

  wrapper.addEventListener("click", (event) => {
    const button = event.target.closest("[data-delta]");
    if (!button) return;
    input.value = String(clampQuantity(Number(input.value || 0) + Number(button.dataset.delta), Number(input.min || 0), Number(input.max || 99)));
    input.dispatchEvent(new Event("input", { bubbles: true }));
    update();
  });
  input.addEventListener("input", update);
  document.querySelector("#locale-select")?.addEventListener("change", () => queueMicrotask(update));
  update();
}

function refresh() {
  document.querySelectorAll("#cart-items .product-card").forEach(enhanceCartCard);
}

const cartItems = document.querySelector("#cart-items");
if (cartItems) new MutationObserver(refresh).observe(cartItems, { childList: true });
refresh();

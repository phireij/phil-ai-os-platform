const copy = {
  en: { decrease: "Decrease quantity", increase: "Increase quantity", lineTotal: "Item total" },
  ja: { decrease: "数量を減らす", increase: "数量を増やす", lineTotal: "商品小計" },
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
  card.querySelector(".product-card-body")?.append(total);

  const update = () => {
    const lang = locale();
    const quantity = clampQuantity(input.value, Number(input.min || 0), Number(input.max || 99));
    input.value = String(quantity);
    total.textContent = `${copy[lang].lineTotal}: ${formatYen(numericUnitPrice(unitPrice.textContent) * quantity, lang)}`;
    const [minus, plus] = wrapper.querySelectorAll(".quantity-step");
    minus.textContent = "−";
    plus.textContent = "+";
    minus.setAttribute("aria-label", copy[lang].decrease);
    plus.setAttribute("aria-label", copy[lang].increase);
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

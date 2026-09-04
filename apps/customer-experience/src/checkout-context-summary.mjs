const copy = {
  en: { label: "Checkout summary", pickup: "Store pickup", delivery: "Delivery", empty: "Cart empty" },
  ja: { label: "チェックアウト概要", pickup: "店頭受取", delivery: "配送", empty: "カートは空です" },
};

function locale() {
  return document.documentElement.lang === "ja" ? "ja" : "en";
}

function fulfillmentLabel() {
  const lang = locale();
  const mode = document.querySelector('input[name="fulfillment-mode"]:checked')?.value || "pickup";
  return mode === "delivery" ? copy[lang].delivery : copy[lang].pickup;
}

function ensureSummary() {
  let bar = document.querySelector("#mobile-checkout-context");
  if (bar) return bar;
  const form = document.querySelector("#cart-form");
  if (!form) return null;
  bar = document.createElement("aside");
  bar.id = "mobile-checkout-context";
  bar.className = "mobile-checkout-context";
  bar.setAttribute("role", "status");
  bar.setAttribute("aria-live", "polite");
  bar.setAttribute("aria-atomic", "true");
  bar.innerHTML = `<span class="mobile-checkout-context-label"></span><strong class="mobile-checkout-context-total"></strong><span class="mobile-checkout-context-fulfillment"></span>`;
  form.prepend(bar);
  return bar;
}

function refresh() {
  const bar = ensureSummary();
  if (!bar) return;
  const lang = locale();
  const source = document.querySelector("#cart-summary")?.textContent?.trim() || copy[lang].empty;
  bar.querySelector(".mobile-checkout-context-label").textContent = copy[lang].label;
  bar.querySelector(".mobile-checkout-context-total").textContent = source;
  bar.querySelector(".mobile-checkout-context-fulfillment").textContent = fulfillmentLabel();
  bar.setAttribute("aria-label", `${copy[lang].label}: ${source}. ${fulfillmentLabel()}`);
}

document.querySelector("#cart-form")?.addEventListener("input", () => queueMicrotask(refresh));
document.querySelector("#cart-form")?.addEventListener("change", () => queueMicrotask(refresh));
document.querySelector("#locale-select")?.addEventListener("change", () => queueMicrotask(refresh));

const cartSummary = document.querySelector("#cart-summary");
if (cartSummary) new MutationObserver(refresh).observe(cartSummary, { childList: true, subtree: true, characterData: true });
const checkout = document.querySelector("#cart-form .checkout-card");
if (checkout) new MutationObserver(refresh).observe(checkout, { childList: true, subtree: true });

refresh();

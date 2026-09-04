const copy = {
  en: {
    chooseItem: "Choose at least one available item to continue.",
    choosePickup: "Choose a preferred pickup time to continue.",
    chooseArea: "Choose a delivery area to continue.",
    ready: "Ready to review the next checkout step.",
  },
  ja: {
    chooseItem: "続行するには利用可能な商品を1つ以上選択してください。",
    choosePickup: "続行するには希望受取時間を選択してください。",
    chooseArea: "続行するには配送地域を選択してください。",
    ready: "次のチェックアウト確認へ進めます。",
  },
};

function locale() {
  return document.documentElement.lang === "ja" ? "ja" : "en";
}

function fulfillmentMode() {
  return document.querySelector('input[name="fulfillment-mode"]:checked')?.value || "pickup";
}

function hasSelectedItems() {
  return [...document.querySelectorAll("#cart-items [data-cart-sku]")].some((input) => {
    const value = Number(input.value);
    return !input.disabled && Number.isInteger(value) && value > 0;
  });
}

function visiblePrerequisite() {
  if (!hasSelectedItems()) return "chooseItem";
  if (fulfillmentMode() === "delivery") {
    return document.querySelector("#delivery-area")?.value ? "ready" : "chooseArea";
  }
  return document.querySelector("#pickup-at")?.value ? "ready" : "choosePickup";
}

function ensureGuidance() {
  let guidance = document.querySelector("#cart-form-guidance");
  if (guidance) return guidance;
  guidance = document.createElement("p");
  guidance.id = "cart-form-guidance";
  guidance.className = "cart-form-guidance";
  guidance.setAttribute("role", "status");
  guidance.setAttribute("aria-live", "polite");
  document.querySelector("#evaluate-button")?.closest("p")?.after(guidance);
  return guidance;
}

function evaluateGuard() {
  const state = visiblePrerequisite();
  const button = document.querySelector("#evaluate-button");
  const guidance = ensureGuidance();
  if (!button || !guidance) return;
  const ready = state === "ready";
  button.disabled = !ready;
  button.setAttribute("aria-disabled", ready ? "false" : "true");
  guidance.textContent = copy[locale()][state];
  guidance.dataset.state = state;
}

const form = document.querySelector("#cart-form");
form?.addEventListener("input", () => queueMicrotask(evaluateGuard));
form?.addEventListener("change", () => queueMicrotask(evaluateGuard));
document.querySelector("#locale-select")?.addEventListener("change", () => queueMicrotask(evaluateGuard));

const cartItems = document.querySelector("#cart-items");
if (cartItems) new MutationObserver(() => queueMicrotask(evaluateGuard)).observe(cartItems, { childList: true, subtree: true });

const checkoutCard = document.querySelector("#cart-form .checkout-card");
if (checkoutCard) new MutationObserver(() => queueMicrotask(evaluateGuard)).observe(checkoutCard, { childList: true, subtree: true });

evaluateGuard();

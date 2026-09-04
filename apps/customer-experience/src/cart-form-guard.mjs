const copy = {
  en: {
    chooseItem: "Choose at least one available item to continue.",
    choosePickup: "Choose a preferred pickup time to continue.",
    chooseArea: "Choose a delivery area to continue.",
    ready: "Ready to review the next checkout step.",
    fix: "Go to required field",
  },
  ja: {
    chooseItem: "続行するには利用可能な商品を1つ以上選択してください。",
    choosePickup: "続行するには希望受取時間を選択してください。",
    chooseArea: "続行するには配送地域を選択してください。",
    ready: "次のチェックアウト確認へ進めます。",
    fix: "必要な項目へ移動",
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

function targetFor(state) {
  if (state === "choosePickup") return document.querySelector("#pickup-at");
  if (state === "chooseArea") return document.querySelector("#delivery-area");
  if (state === "chooseItem") {
    return [...document.querySelectorAll("#cart-items [data-cart-sku]")].find((input) => !input.disabled) || null;
  }
  return null;
}

function focusRequiredField(state) {
  const target = targetFor(state);
  if (!target) return false;
  target.scrollIntoView({ block: "center", behavior: "smooth" });
  target.focus({ preventScroll: true });
  return true;
}

function ensureGuidance() {
  let guidance = document.querySelector("#cart-form-guidance");
  if (guidance) return guidance;
  guidance = document.createElement("div");
  guidance.id = "cart-form-guidance";
  guidance.className = "cart-form-guidance";
  guidance.setAttribute("role", "status");
  guidance.setAttribute("aria-live", "polite");
  guidance.setAttribute("aria-atomic", "true");
  document.querySelector("#evaluate-button")?.closest("p")?.after(guidance);
  return guidance;
}

function renderGuidance(guidance, state) {
  guidance.replaceChildren();
  const message = document.createElement("span");
  message.textContent = copy[locale()][state];
  guidance.append(message);

  if (state !== "ready" && targetFor(state)) {
    const action = document.createElement("button");
    action.type = "button";
    action.className = "cart-guidance-action";
    action.textContent = copy[locale()].fix;
    action.addEventListener("click", () => focusRequiredField(state));
    guidance.append(action);
  }
}

function evaluateGuard() {
  const state = visiblePrerequisite();
  const button = document.querySelector("#evaluate-button");
  const guidance = ensureGuidance();
  if (!button || !guidance) return;
  const ready = state === "ready";
  button.disabled = !ready;
  button.setAttribute("aria-disabled", ready ? "false" : "true");
  button.setAttribute("aria-describedby", "cart-form-guidance");
  guidance.dataset.state = state;
  renderGuidance(guidance, state);
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

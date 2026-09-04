import { localeHref } from "./locale-links.mjs";

const copy = {
  en: {
    action: "Browse products",
    hint: "Your cart is empty. Browse the catalog and choose a product to continue.",
  },
  ja: {
    action: "商品を見る",
    hint: "カートは空です。商品一覧から商品を選んで続行してください。",
  },
};

function locale() {
  return document.documentElement.lang === "ja" ? "ja" : "en";
}

function selectedQuantityTotal() {
  return [...document.querySelectorAll("[data-cart-sku]")].reduce((total, input) => {
    if (input.disabled) return total;
    const quantity = Number(input.value || 0);
    return total + (Number.isFinite(quantity) && quantity > 0 ? quantity : 0);
  }, 0);
}

function ensureRecovery() {
  const summary = document.querySelector("#cart-summary");
  if (!summary) return null;
  let recovery = document.querySelector("#empty-cart-recovery");
  if (!recovery) {
    recovery = document.createElement("div");
    recovery.id = "empty-cart-recovery";
    recovery.className = "empty-cart-recovery";
    recovery.setAttribute("role", "status");
    recovery.setAttribute("aria-live", "polite");
    recovery.setAttribute("aria-atomic", "true");
    recovery.innerHTML = `<span class="empty-cart-recovery-hint"></span><a class="primary-button empty-cart-recovery-action"></a>`;
    summary.insertAdjacentElement("afterend", recovery);
  }
  return recovery;
}

function refresh() {
  const recovery = ensureRecovery();
  if (!recovery) return;
  const isEmpty = selectedQuantityTotal() === 0;
  recovery.hidden = !isEmpty;
  if (!isEmpty) return;

  const lang = locale();
  recovery.querySelector(".empty-cart-recovery-hint").textContent = copy[lang].hint;
  const action = recovery.querySelector(".empty-cart-recovery-action");
  action.textContent = copy[lang].action;
  action.href = localeHref("./#catalog-section", lang);
}

const form = document.querySelector("#cart-form");
form?.addEventListener("input", refresh);
form?.addEventListener("change", refresh);
document.querySelector("#locale-select")?.addEventListener("change", () => queueMicrotask(refresh));

const items = document.querySelector("#cart-items");
if (items) new MutationObserver(() => queueMicrotask(refresh)).observe(items, { childList: true, subtree: true });

refresh();

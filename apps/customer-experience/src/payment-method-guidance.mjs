const copy = {
  en: {
    title: "Payment method guidance",
    intro: "Review how the selected payment method works before final confirmation.",
    method: "Preview payment method",
    konbini: "Konbini",
    konbiniTiming: "Pay within 3 days. The transaction-specific deadline shown by KOMOJU controls.",
    konbiniNext: "After order submission in the future governed flow, KOMOJU will provide the payment instructions and exact deadline.",
    safety: "Preview only · no payment is created or executed here.",
  },
  ja: {
    title: "お支払い方法のご案内",
    intro: "最終確認の前に、選択したお支払い方法の流れをご確認ください。",
    method: "プレビューのお支払い方法",
    konbini: "コンビニ決済",
    konbiniTiming: "3日以内にお支払いください。実際はKOMOJUが注文ごとに表示する期限が優先されます。",
    konbiniNext: "将来のガバナンス済み注文フローでは、注文送信後にKOMOJUから支払方法と正確な期限が案内されます。",
    safety: "プレビューのみ・ここでは決済の作成や実行は行いません。",
  },
};

function locale() {
  return document.documentElement.lang === "ja" ? "ja" : "en";
}

async function loadPaymentPreview() {
  const response = await fetch("./fixtures/final-confirmation.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`payment guidance fixture failed: ${response.status}`);
  const fixture = await response.json();
  if (fixture.fixture_only !== true || fixture.preview_only !== true) {
    throw new Error("payment guidance requires fixture-only preview data");
  }
  if (fixture.payment_execution_authorized !== false || fixture.order_creation_authorized !== false) {
    throw new Error("payment guidance must remain non-authorizing");
  }
  return fixture.payment;
}

let payment = null;

function render() {
  const root = document.querySelector("#payment-method-guidance");
  if (!root || !payment) return;
  const lang = locale();
  const c = copy[lang];
  root.querySelector("#payment-guidance-title").textContent = c.title;
  root.querySelector("#payment-guidance-intro").textContent = c.intro;
  root.querySelector("#payment-guidance-method-label").textContent = c.method;
  root.querySelector("#payment-guidance-method").textContent = payment.method === "konbini" ? c.konbini : String(payment.method || "—");
  root.querySelector("#payment-guidance-timing").textContent = payment.method === "konbini" && payment.expiry_days === 3 ? c.konbiniTiming : "";
  root.querySelector("#payment-guidance-next").textContent = payment.method === "konbini" ? c.konbiniNext : "";
  root.querySelector("#payment-guidance-safety").textContent = c.safety;
}

async function install() {
  const checkout = document.querySelector("#cart-form .checkout-card");
  if (!checkout || document.querySelector("#payment-method-guidance")) return;
  const section = document.createElement("section");
  section.id = "payment-method-guidance";
  section.className = "payment-method-guidance";
  section.setAttribute("aria-labelledby", "payment-guidance-title");
  section.innerHTML = `
    <h3 id="payment-guidance-title"></h3>
    <p id="payment-guidance-intro"></p>
    <dl class="payment-guidance-list">
      <div><dt id="payment-guidance-method-label"></dt><dd id="payment-guidance-method"></dd></div>
    </dl>
    <p id="payment-guidance-timing" class="payment-guidance-highlight"></p>
    <p id="payment-guidance-next"></p>
    <p id="payment-guidance-safety" class="checkout-reassurance"></p>`;
  checkout.insertBefore(section, checkout.querySelector(".checkout-reassurance"));
  try {
    payment = await loadPaymentPreview();
    render();
  } catch {
    section.remove();
    return;
  }
  document.querySelector("#locale-select")?.addEventListener("change", () => queueMicrotask(render));
}

install();

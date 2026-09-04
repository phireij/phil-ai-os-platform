const copy = {
  en: {
    title: "Final review at a glance",
    total: "Total",
    fulfillment: "Fulfillment",
    payment: "Payment",
    cancellation: "Cancellation",
    returns: "Returns / defects",
    deadline: (days) => `Konbini: pay within ${days} days; the transaction-specific KOMOJU deadline controls.`,
    safety: "Preview only · no order submission or payment execution.",
  },
  ja: {
    title: "最終確認の要点",
    total: "合計",
    fulfillment: "受取・配送",
    payment: "お支払い",
    cancellation: "キャンセル",
    returns: "返品・不良品",
    deadline: (days) => `コンビニ決済：${days}日以内にお支払いください。実際はKOMOJUが注文ごとに表示する期限が優先されます。`,
    safety: "プレビューのみ・注文送信や決済実行は行いません。",
  },
};

function locale() {
  return document.documentElement.lang === "ja" ? "ja" : "en";
}

function yen(value, lang) {
  return new Intl.NumberFormat(lang === "ja" ? "ja-JP" : "en-US", { style: "currency", currency: "JPY", maximumFractionDigits: 0 }).format(value);
}

let fixture = null;

function localized(value, lang) {
  return value?.[lang] || value?.en || "—";
}

function render() {
  const root = document.querySelector("#final-review-summary");
  if (!root || !fixture) return;
  const lang = locale();
  const c = copy[lang];
  root.querySelector("#final-review-summary-title").textContent = c.title;
  root.querySelector("#final-review-total-label").textContent = c.total;
  root.querySelector("#final-review-total").textContent = yen(fixture.pricing.total_jpy, lang);
  root.querySelector("#final-review-fulfillment-label").textContent = c.fulfillment;
  root.querySelector("#final-review-fulfillment").textContent = localized(fixture.fulfillment.summary, lang);
  root.querySelector("#final-review-payment-label").textContent = c.payment;
  root.querySelector("#final-review-payment").textContent = fixture.payment.method === "konbini"
    ? `${localized(fixture.payment.label, lang)} · ${c.deadline(fixture.payment.expiry_days)}`
    : localized(fixture.payment.label, lang);
  root.querySelector("#final-review-cancellation-label").textContent = c.cancellation;
  root.querySelector("#final-review-cancellation").textContent = localized(fixture.cancellation.summary, lang);
  root.querySelector("#final-review-returns-label").textContent = c.returns;
  root.querySelector("#final-review-returns").textContent = localized(fixture.returns.summary, lang);
  root.querySelector("#final-review-safety").textContent = c.safety;
}

async function install() {
  const hero = document.querySelector("main .hero");
  if (!hero || document.querySelector("#final-review-summary")) return;
  const response = await fetch("./fixtures/final-confirmation.json", { cache: "no-store" });
  if (!response.ok) return;
  const payload = await response.json();
  if (
    payload.fixture_only !== true ||
    payload.preview_only !== true ||
    payload.order_creation_authorized !== false ||
    payload.payment_execution_authorized !== false ||
    payload.production_publish_authorized !== false
  ) return;
  fixture = payload;

  const section = document.createElement("section");
  section.id = "final-review-summary";
  section.className = "final-review-summary";
  section.setAttribute("aria-labelledby", "final-review-summary-title");
  section.innerHTML = `
    <h2 id="final-review-summary-title"></h2>
    <dl class="final-review-summary-grid">
      <div><dt id="final-review-total-label"></dt><dd id="final-review-total"></dd></div>
      <div><dt id="final-review-fulfillment-label"></dt><dd id="final-review-fulfillment"></dd></div>
      <div><dt id="final-review-payment-label"></dt><dd id="final-review-payment"></dd></div>
      <div><dt id="final-review-cancellation-label"></dt><dd id="final-review-cancellation"></dd></div>
      <div><dt id="final-review-returns-label"></dt><dd id="final-review-returns"></dd></div>
    </dl>
    <p id="final-review-safety" class="checkout-reassurance"></p>`;
  hero.after(section);
  render();
  document.querySelector("#locale-select")?.addEventListener("change", () => queueMicrotask(render));
}

install().catch(() => undefined);

const copy = {
  en: {
    legend: "How would you like to receive your order?",
    pickup: "Store pickup",
    pickupCopy: "Choose a preferred pickup time. Final availability is confirmed before submission.",
    delivery: "Delivery",
    deliveryCopy: "Yamato Cool delivery. Shipping is shown before the final order action.",
    area: "Delivery area",
    kanto: "Kanto",
    other: "Other regions",
    kantoFee: "Kanto: ¥1,350 flat rate",
    otherFee: "Other regions: ¥1,500–¥1,800 depending on delivery area",
    exactFee: "The exact shipping fee will be displayed on the final order confirmation screen before the order is submitted.",
    reviewDelivery: "Review delivery readiness",
    deliveryTitle: "Delivery path preview",
    deliveryReady: "Delivery preference recorded locally for review only.",
    deliveryPending: "Select a delivery area to review the shipping guidance.",
    noHandoff: "No order or payment handoff was prepared for delivery in this isolated preview.",
  },
  ja: {
    legend: "商品の受け取り方法を選択してください",
    pickup: "店頭受取",
    pickupCopy: "希望受取時間を選択してください。最終的な受取可否は注文確定前に確認されます。",
    delivery: "配送",
    deliveryCopy: "ヤマト運輸クール便。送料はご注文確定前に表示されます。",
    area: "配送地域",
    kanto: "関東",
    other: "その他の地域",
    kantoFee: "関東：一律 1,350円",
    otherFee: "その他の地域：配送地域により 1,500円〜1,800円",
    exactFee: "最終的な送料は、ご注文確定前の最終確認画面に表示されます。",
    reviewDelivery: "配送内容を確認",
    deliveryTitle: "配送プレビュー",
    deliveryReady: "配送希望をローカルプレビューに記録しました。",
    deliveryPending: "送料案内を確認するため配送地域を選択してください。",
    noHandoff: "この分離プレビューでは、配送注文または決済引継ぎは作成されていません。",
  },
};

function locale() {
  return document.documentElement.lang === "ja" ? "ja" : "en";
}

function selectedMode() {
  return document.querySelector('input[name="fulfillment-mode"]:checked')?.value || "pickup";
}

function renderDeliveryResult() {
  const lang = locale();
  const area = document.querySelector("#delivery-area")?.value || "";
  const title = document.querySelector("#result-title");
  const result = document.querySelector("#result");
  if (!title || !result) return;
  title.textContent = copy[lang].deliveryTitle;
  const fee = area === "kanto" ? copy[lang].kantoFee : area === "other" ? copy[lang].otherFee : "";
  const status = fee ? copy[lang].deliveryReady : copy[lang].deliveryPending;
  result.innerHTML = `<p><strong>${status}</strong></p>${fee ? `<p>${fee}</p><p>${copy[lang].exactFee}</p>` : ""}<p>${copy[lang].noHandoff}</p>`;
}

function updateMode() {
  const lang = locale();
  const mode = selectedMode();
  const pickupField = document.querySelector("#pickup-at")?.closest(".form-field");
  const pickupInput = document.querySelector("#pickup-at");
  const deliveryPanel = document.querySelector("#delivery-options");
  const button = document.querySelector("#evaluate-button");
  if (pickupField) pickupField.hidden = mode !== "pickup";
  if (pickupInput) pickupInput.required = mode === "pickup";
  if (deliveryPanel) deliveryPanel.hidden = mode !== "delivery";
  if (button && mode === "delivery") button.textContent = copy[lang].reviewDelivery;
  document.querySelectorAll(".fulfillment-option").forEach((option) => {
    const radio = option.querySelector('input[name="fulfillment-mode"]');
    option.classList.toggle("is-selected", Boolean(radio?.checked));
  });
}

function localize() {
  const lang = locale();
  const root = document.querySelector("#fulfillment-choice");
  if (!root) return;
  root.querySelector("legend").textContent = copy[lang].legend;
  root.querySelector("#fulfillment-pickup-title").textContent = copy[lang].pickup;
  root.querySelector("#fulfillment-pickup-copy").textContent = copy[lang].pickupCopy;
  root.querySelector("#fulfillment-delivery-title").textContent = copy[lang].delivery;
  root.querySelector("#fulfillment-delivery-copy").textContent = copy[lang].deliveryCopy;
  root.querySelector("#delivery-area-label").textContent = copy[lang].area;
  root.querySelector('#delivery-area option[value="kanto"]').textContent = copy[lang].kanto;
  root.querySelector('#delivery-area option[value="other"]').textContent = copy[lang].other;
  root.querySelector("#shipping-kanto-copy").textContent = copy[lang].kantoFee;
  root.querySelector("#shipping-other-copy").textContent = copy[lang].otherFee;
  root.querySelector("#shipping-exact-copy").textContent = copy[lang].exactFee;
  updateMode();
}

function install() {
  const checkout = document.querySelector("#cart-form .checkout-card");
  if (!checkout || document.querySelector("#fulfillment-choice")) return;
  const fieldset = document.createElement("fieldset");
  fieldset.id = "fulfillment-choice";
  fieldset.className = "fulfillment-choice";
  fieldset.innerHTML = `
    <legend></legend>
    <div class="fulfillment-option-grid">
      <label class="fulfillment-option is-selected"><input type="radio" name="fulfillment-mode" value="pickup" checked><span><strong id="fulfillment-pickup-title"></strong><small id="fulfillment-pickup-copy"></small></span></label>
      <label class="fulfillment-option"><input type="radio" name="fulfillment-mode" value="delivery"><span><strong id="fulfillment-delivery-title"></strong><small id="fulfillment-delivery-copy"></small></span></label>
    </div>
    <div id="delivery-options" class="delivery-options" hidden>
      <label id="delivery-area-label" for="delivery-area"></label>
      <select id="delivery-area"><option value="">—</option><option value="kanto"></option><option value="other"></option></select>
      <div class="shipping-guidance" aria-live="polite"><p id="shipping-kanto-copy"></p><p id="shipping-other-copy"></p><p id="shipping-exact-copy"></p></div>
    </div>`;
  checkout.prepend(fieldset);
  fieldset.addEventListener("change", updateMode);
  document.querySelector("#delivery-area")?.addEventListener("change", renderDeliveryResult);
  localize();

  document.querySelector("#cart-form")?.addEventListener("submit", (event) => {
    if (selectedMode() !== "delivery") return;
    event.preventDefault();
    event.stopImmediatePropagation();
    renderDeliveryResult();
  }, true);
  document.querySelector("#locale-select")?.addEventListener("change", () => queueMicrotask(localize));
}

install();

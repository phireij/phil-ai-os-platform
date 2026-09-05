const form = document.querySelector("#order-intake-form");
const cakeType = document.querySelector("#cake-type");
const customFields = document.querySelector("#custom-cake-fields");
const requestedDate = document.querySelector("#requested-date");
const yamatoWindow = document.querySelector("#yamato-window");
const yamatoWindowField = document.querySelector("#yamato-window-field");
const referenceImages = document.querySelector("#reference-images");
const status = document.querySelector("#intake-status");

const summaryFulfillment = document.querySelector("#summary-fulfillment");
const summaryDate = document.querySelector("#summary-date");
const summaryWindow = document.querySelector("#summary-window");
const summaryCake = document.querySelector("#summary-cake");

const fulfillmentLabels = {
  yamato: "Yamato",
  "ruby-car": "Ruby car",
  pickup: "Shop pickup",
};

function selectedFulfillment() {
  return form.querySelector('input[name="fulfillment"]:checked')?.value || "yamato";
}

function renderCustomFields() {
  const custom = cakeType.value === "custom";
  customFields.hidden = !custom;
  summaryCake.textContent = custom ? "Custom / オーダー" : "Basic / ベーシック";
}

function renderFulfillment() {
  const method = selectedFulfillment();
  summaryFulfillment.textContent = fulfillmentLabels[method] || method;
  const isYamato = method === "yamato";
  yamatoWindowField.hidden = !isYamato;
  summaryWindow.textContent = isYamato
    ? yamatoWindow.options[yamatoWindow.selectedIndex]?.textContent || "No preference"
    : "Not applicable";
}

function renderDate() {
  summaryDate.textContent = requestedDate.value || "Not selected";
}

function renderWindow() {
  if (selectedFulfillment() !== "yamato") return;
  summaryWindow.textContent =
    yamatoWindow.options[yamatoWindow.selectedIndex]?.textContent || "No preference";
}

function validateReferenceImages() {
  const files = Array.from(referenceImages.files || []);
  if (files.length > 8) {
    referenceImages.setCustomValidity("Please select no more than 8 reference images.");
    return false;
  }
  const allowed = new Set(["image/jpeg", "image/png", "image/webp"]);
  if (files.some((file) => !allowed.has(file.type))) {
    referenceImages.setCustomValidity("Only JPEG, PNG, and WebP reference images are accepted.");
    return false;
  }
  referenceImages.setCustomValidity("");
  return true;
}

form.addEventListener("change", (event) => {
  if (event.target === cakeType) renderCustomFields();
  if (event.target.matches('input[name="fulfillment"]')) renderFulfillment();
  if (event.target === requestedDate) renderDate();
  if (event.target === yamatoWindow) renderWindow();
  if (event.target === referenceImages) validateReferenceImages();
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  validateReferenceImages();
  renderFulfillment();
  renderDate();
  renderWindow();
  renderCustomFields();

  if (!form.checkValidity()) {
    form.reportValidity();
    status.textContent = "Please review the required fields. / 必須項目をご確認ください。";
    return;
  }

  status.textContent =
    "Preview only: request captured locally. Delivery and final quote still require confirmation before payment. / プレビューのみ：配達と最終金額の確定後にお支払いをご案内します。";
});

renderCustomFields();
renderFulfillment();
renderDate();
renderWindow();

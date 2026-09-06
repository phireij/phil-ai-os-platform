const form = document.querySelector("#order-intake-form");
const cakeType = document.querySelector("#cake-type");
const customFields = document.querySelector("#custom-cake-fields");
const requestedDate = document.querySelector("#requested-date");
const requestedDateLabel = document.querySelector("#requested-date-label");
const requestedDateHelp = document.querySelector("#requested-date-help");
const deliveryTitle = document.querySelector("#delivery-title");
const summaryDateLabel = document.querySelector("#summary-date-label");
const yamatoWindow = document.querySelector("#yamato-window");
const yamatoWindowField = document.querySelector("#yamato-window-field");
const rubyCarRouteGuidance = document.querySelector("#ruby-car-route-guidance");
const referenceImages = document.querySelector("#reference-images");
const status = document.querySelector("#intake-status");

const summaryFulfillment = document.querySelector("#summary-fulfillment");
const summaryDate = document.querySelector("#summary-date");
const summaryWindow = document.querySelector("#summary-window");
const summaryRoute = document.querySelector("#summary-route");
const summaryCake = document.querySelector("#summary-cake");

const fulfillmentLabels = {
  yamato: "Yamato",
  "ruby-car": "Ruby car",
  pickup: "Shop pickup",
};

const requestedDateCopy = {
  delivery: {
    title: "2. Requested delivery / 希望配達",
    label: "Requested delivery date / 希望配達日",
    help: "This is a request, not a confirmed delivery date. / ご希望の配達日であり、確定日ではありません。",
    summary: "Requested delivery date",
  },
  pickup: {
    title: "2. Requested pickup / 希望受取",
    label: "Requested pickup date / 希望受取日",
    help: "This is a request, not a confirmed pickup date. / ご希望の受取日であり、確定日ではありません。",
    summary: "Requested pickup date",
  },
};

function selectedFulfillment() {
  return form.querySelector('input[name="fulfillment"]:checked')?.value || "yamato";
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

function renderCustomFields() {
  const custom = cakeType.value === "custom";
  customFields.hidden = !custom;
  customFields
    .querySelectorAll("input, select, textarea, button")
    .forEach((control) => {
      control.disabled = !custom;
    });
  if (custom) {
    validateReferenceImages();
  } else {
    referenceImages.setCustomValidity("");
  }
  summaryCake.textContent = custom ? "Custom / オーダー" : "Basic / ベーシック";
}

function renderFulfillment() {
  const method = selectedFulfillment();
  summaryFulfillment.textContent = fulfillmentLabels[method] || method;
  const isYamato = method === "yamato";
  const isRubyCar = method === "ruby-car";
  const dateCopy = method === "pickup" ? requestedDateCopy.pickup : requestedDateCopy.delivery;
  deliveryTitle.textContent = dateCopy.title;
  requestedDateLabel.textContent = dateCopy.label;
  requestedDateHelp.textContent = dateCopy.help;
  summaryDateLabel.textContent = dateCopy.summary;
  yamatoWindowField.hidden = !isYamato;
  yamatoWindow.disabled = !isYamato;
  rubyCarRouteGuidance.hidden = !isRubyCar;
  summaryWindow.textContent = isYamato
    ? yamatoWindow.options[yamatoWindow.selectedIndex]?.textContent || "No preference"
    : "Not applicable";
  summaryRoute.textContent = isRubyCar
    ? "Pending route review — no live calculation / ルート確認待ち（ライブ計算なし）"
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
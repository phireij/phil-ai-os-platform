import { firstPartyQuickPickupUiState, validateFirstPartyQuickPickupConfig } from "./pickup.mjs";
import { applyQuickPickupDisableControl, validateQuickPickupDisableControl } from "./quick-pickup-disable-control.mjs";
import {
  buildDeterministicQuickPickupFixtureRequest,
  evaluateQuickPickupDecisionPreview,
} from "./quick-pickup-decision-preview.mjs";
import { quickPickupRouteCopy, validateQuickPickupRouteCopy } from "./quick-pickup-route-copy.mjs";
import { syncLocaleLinks } from "./locale-links.mjs";

let locale = new URLSearchParams(location.search).get("lang") === "ja" ? "ja" : "en";
let config;
let disableControl;
let decision;
let controlledRouteState;
const localeSelect = document.querySelector("#locale-select");
const routeOutput = document.querySelector("#route-output");
const fixtureOutput = document.querySelector("#fixture-output");

function render() {
  const c = quickPickupRouteCopy(locale);
  document.documentElement.lang = locale;
  localeSelect.value = locale;
  localeSelect.setAttribute("aria-label", c.language);
  document.querySelector(".locale-label").textContent = c.language;
  document.querySelector("#route-status").textContent = c.status;
  document.querySelector("#hero-title").textContent = c.hero;
  document.querySelector("#hero-copy").textContent = c.heroCopy;
  document.querySelector("#route-title").textContent = c.routeTitle;
  document.querySelector("#safety-title").textContent = c.fixtureTitle;
  document.querySelector("#dock-shop-label").textContent = c.shop;
  document.querySelector("#dock-cart-label").textContent = c.cart;
  document.querySelector("#dock-pickup-label").textContent = c.pickup;
  document.querySelector(".mobile-action-dock").setAttribute("aria-label", c.nav);
  document.querySelector("#footer-copy").textContent = c.footer;
  syncLocaleLinks(locale);

  routeOutput.replaceChildren();
  const routeMessage = document.createElement("strong");
  routeMessage.textContent = controlledRouteState.reason === "operator_disable_engaged" ? c.routeDisabled : c.routePending;
  routeOutput.append(routeMessage);

  const routeTechnical = document.createElement("pre");
  routeTechnical.textContent = JSON.stringify({
    route_implemented: config.route_implemented,
    customer_route_configured: Boolean(config.customer_route),
    route_available: controlledRouteState.available,
    href_exposed: Boolean(controlledRouteState.href),
    route_reason: controlledRouteState.reason,
    activation_authorized: config.activation_authorized,
    operator_disable_engaged: disableControl.disable_engaged,
    order_creation_authorized: false,
    payment_execution_authorized: false,
    production_publish_authorized: false,
  }, null, 2);
  routeOutput.append(routeTechnical);

  fixtureOutput.replaceChildren();
  const fixtureResult = document.createElement("strong");
  fixtureResult.textContent = decision.available ? c.fixtureAvailable : c.fixtureBlocked;
  const fixtureSafety = document.createElement("p");
  fixtureSafety.textContent = c.fixtureSafety;
  fixtureOutput.append(fixtureResult, fixtureSafety);
}

async function boot() {
  validateQuickPickupRouteCopy();
  const [configResponse, inventoryResponse, capacityResponse, disableResponse] = await Promise.all([
    fetch("./fixtures/first-party-quick-pickup.json", { cache: "no-store" }),
    fetch("./fixtures/quick-pickup-inventory-snapshot.json", { cache: "no-store" }),
    fetch("./fixtures/quick-pickup-capacity-snapshot.json", { cache: "no-store" }),
    fetch("./fixtures/quick-pickup-disable-control.json", { cache: "no-store" }),
  ]);
  for (const response of [configResponse, inventoryResponse, capacityResponse, disableResponse]) {
    if (!response.ok) throw new Error(`Quick Pickup route fixture failed: ${response.status}`);
  }

  const [inventory, capacity] = await Promise.all([inventoryResponse.json(), capacityResponse.json()]);
  config = await configResponse.json();
  disableControl = await disableResponse.json();
  validateFirstPartyQuickPickupConfig(config);
  validateQuickPickupDisableControl(disableControl);

  const routeState = firstPartyQuickPickupUiState(config);
  controlledRouteState = applyQuickPickupDisableControl(routeState, disableControl);
  const request = buildDeterministicQuickPickupFixtureRequest(inventory, capacity);
  decision = evaluateQuickPickupDecisionPreview(request, inventory, capacity);
  render();

  localeSelect.addEventListener("change", () => {
    locale = localeSelect.value === "ja" ? "ja" : "en";
    const url = new URL(location.href);
    url.searchParams.set("lang", locale);
    history.replaceState(null, "", url);
    render();
  });
}

boot().catch(() => {
  routeOutput.textContent = quickPickupRouteCopy(locale).loadFailure;
  routeOutput.setAttribute("role", "alert");
});

import { chromium } from "playwright";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const EXPECTED_HOST = "darkgreen-wallaby-680439.hostingersite.com";
const baseUrl = (process.env.RUBY_WOO_PREPRODUCTION_BASE_URL || "").replace(/\/$/, "");
const outputDir = process.env.RUBY_FINAL_SCREEN_CAPTURE_OUTPUT || "/tmp/philaios-ruby-final-screen";

if (!baseUrl) throw new Error("RUBY_WOO_PREPRODUCTION_BASE_URL is required");
const target = new URL(baseUrl);
if (target.protocol !== "https:" || target.hostname !== EXPECTED_HOST) {
  throw new Error(`capture target must remain locked to https://${EXPECTED_HOST}`);
}

const synthetic = Object.freeze({
  firstName: "QA",
  lastName: "Synthetic",
  email: "qa-preproduction@example.invalid",
  phone: "09000000000",
  postcode: "1000001",
  city: "Chiyoda-ku",
  address1: "1-1-1 Synthetic QA",
});

const blockedRequests = [];
const allowedSessionMutations = [];

function classifyRequest(request) {
  const method = request.method().toUpperCase();
  const url = new URL(request.url());
  const wcAjax = url.searchParams.get("wc-ajax") || "";
  const p = url.pathname.toLowerCase();
  const host = url.hostname.toLowerCase();

  if (["PUT", "PATCH", "DELETE"].includes(method)) {
    return { block: true, reason: `forbidden_method_${method}` };
  }
  if (method === "POST") {
    if (host.includes("komoju")) return { block: true, reason: "komoju_post_blocked" };
    if (wcAjax.toLowerCase() === "checkout") return { block: true, reason: "woocommerce_place_order_ajax_blocked" };
    if (/\/wp-json\/wc\/(?:store\/v1\/checkout|v[23]\/orders)(?:\/|$)/.test(p)) {
      return { block: true, reason: "woocommerce_order_endpoint_blocked" };
    }
    if (host !== EXPECTED_HOST) return { block: true, reason: "external_post_blocked" };
    if (wcAjax === "update_order_review" || p.includes("/wp-json/wc/store/v1/cart")) {
      return { block: false, sessionOnly: true, reason: "ephemeral_cart_or_checkout_review" };
    }
    return { block: true, reason: "unclassified_preproduction_post_blocked" };
  }
  return { block: false, sessionOnly: false, reason: "read_only" };
}

function redactText(value) {
  let text = String(value || "");
  const replacements = [
    synthetic.firstName,
    synthetic.lastName,
    synthetic.email,
    synthetic.phone,
    synthetic.postcode,
    synthetic.city,
    synthetic.address1,
  ];
  for (const token of replacements) text = text.split(token).join("[SYNTHETIC_REDACTED]");
  text = text.replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, "[EMAIL_REDACTED]");
  text = text.replace(/(?<!\d)0\d{1,4}[- ]?\d{1,4}[- ]?\d{3,4}(?!\d)/g, "[PHONE_REDACTED]");
  return text;
}

async function fillFirstVisible(page, selectors, value) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    if ((await locator.count()) && (await locator.isVisible().catch(() => false))) {
      await locator.fill(value).catch(() => {});
      return locator;
    }
  }
  return null;
}

async function selectFirstVisible(page, selectors, value) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    if ((await locator.count()) && (await locator.isVisible().catch(() => false))) {
      await locator.selectOption(value).catch(() => {});
      return locator;
    }
  }
  return null;
}

function hasAll(text, patterns) {
  return patterns.every((pattern) => pattern.test(text));
}

function observationDraft(text, linkText, finalActionText) {
  const combined = `${text}\n${linkText}`;
  const productQty = /(quantity|qty|数量|×\s*\d|x\s*\d)/i.test(combined);
  const totals = hasAll(combined, [/(subtotal|小計)/i, /(shipping|配送|送料|受取)/i, /(total|合計)/i]);
  const payment = /(visa|mastercard|jcb|american express|diners|discover|credit card|カード|コンビニ|konbini|merpay|メルペイ|paidy|ペイディ)/i.test(combined);
  const paymentTiming = /(支払|決済|payment|期限|deadline|3\s*days|3日|翌月27日)/i.test(combined);
  const fulfillment = /(配送|送料|shipping|delivery|pickup|受取)/i.test(combined);
  const cancellation = /(キャンセル|返品|返金|cancellation|returns?|refund|特定商取引)/i.test(combined);
  const correction = /(cart|カート|変更|修正|edit|戻る|back)/i.test(combined);
  const finalAction = /(place order|注文する|注文を確定|購入する|注文確定)/i.test(finalActionText || "");
  const tokushoho = /(特定商取引|specified commercial transactions|tokushoho)/i.test(linkText);
  const tax = /(免税|tax[- ]?exempt|適格請求書発行事業者ではありません)/i.test(combined);
  const konbini3 = /(コンビニ|konbini)/i.test(combined) && /(3\s*days|3日)/i.test(combined);
  return {
    product_name_quantity_options_visible: productQty,
    subtotal_shipping_total_visible: totals,
    payment_method_visible: payment,
    payment_timing_or_deadline_visible: paymentTiming,
    fulfillment_timing_visible: fulfillment,
    cancellation_returns_terms_visible_or_linked: cancellation,
    correction_path_available_before_submission: correction,
    final_action_label_unambiguous: finalAction,
    final_action_not_invoked: true,
    tokushoho_disclosure_visible_or_linked: tokushoho,
    tax_display_matches_exempt_posture: tax,
    konbini_three_day_deadline_reconciled_when_selected: konbini3,
  };
}

async function sha256(file) {
  const data = await readFile(file);
  return createHash("sha256").update(data).digest("hex");
}

await mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  locale: "ja-JP",
  userAgent: "PhilAIOS-Preproduction-Final-Screen-QA/1.0",
  viewport: { width: 1440, height: 1100 },
});
const page = await context.newPage();

await page.route("**/*", async (route) => {
  const classification = classifyRequest(route.request());
  if (classification.block) {
    blockedRequests.push({ method: route.request().method(), url_class: new URL(route.request().url()).hostname, reason: classification.reason });
    await route.abort("blockedbyclient");
    return;
  }
  if (classification.sessionOnly) allowedSessionMutations.push(classification.reason);
  await route.continue();
});

try {
  const productResponse = await context.request.get(`${baseUrl}/wp-json/wc/store/v1/products?per_page=20`);
  if (!productResponse.ok()) throw new Error(`preproduction Store API products GET failed: ${productResponse.status()}`);
  const products = await productResponse.json();
  if (!Array.isArray(products)) throw new Error("preproduction Store API products payload is not an array");
  const product = products.find((item) => item?.id && item?.is_purchasable !== false && item?.is_in_stock !== false);
  if (!product) throw new Error("no purchasable preproduction product is available for a session-only checkout review");

  // WooCommerce's add-to-cart query mutates only this disposable browser cart/session.
  await page.goto(`${baseUrl}/?add-to-cart=${encodeURIComponent(product.id)}&quantity=1`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.goto(`${baseUrl}/checkout/`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(2500);

  const currentHost = new URL(page.url()).hostname;
  if (currentHost !== EXPECTED_HOST) throw new Error(`checkout navigated outside preproduction host: ${currentHost}`);

  const bodyBefore = await page.locator("body").innerText().catch(() => "");
  if (/cart is currently empty|カートは現在空です/i.test(bodyBefore)) {
    throw new Error("preproduction checkout cart is empty after session-only add-to-cart preparation");
  }

  const maskLocators = [];
  const candidates = [
    ["#billing_first_name", "input[name='billing_first_name']", "input[id*='billing-first']"],
    ["#billing_last_name", "input[name='billing_last_name']", "input[id*='billing-last']"],
    ["#billing_email", "input[name='billing_email']", "input[type='email']"],
    ["#billing_phone", "input[name='billing_phone']", "input[type='tel']"],
    ["#billing_postcode", "input[name='billing_postcode']", "input[id*='postcode']"],
    ["#billing_city", "input[name='billing_city']", "input[id*='city']"],
    ["#billing_address_1", "input[name='billing_address_1']", "input[id*='address-1']"],
  ];
  const values = [synthetic.firstName, synthetic.lastName, synthetic.email, synthetic.phone, synthetic.postcode, synthetic.city, synthetic.address1];
  for (let i = 0; i < candidates.length; i += 1) {
    const locator = await fillFirstVisible(page, candidates[i], values[i]);
    if (locator) maskLocators.push(locator);
  }
  const country = await selectFirstVisible(page, ["#billing_country", "select[name='billing_country']"], "JP");
  if (country) maskLocators.push(country);
  await selectFirstVisible(page, ["#billing_state", "select[name='billing_state']"], "JP13");

  await page.waitForTimeout(3500);

  const finalActionSelectors = [
    "#place_order",
    "button[name='woocommerce_checkout_place_order']",
    ".wc-block-components-checkout-place-order-button",
  ];
  let finalActionText = "";
  let finalActionFound = false;
  for (const selector of finalActionSelectors) {
    const locator = page.locator(selector).first();
    if ((await locator.count()) && (await locator.isVisible().catch(() => false))) {
      finalActionText = (await locator.innerText().catch(() => "")).trim();
      finalActionFound = true;
      break;
    }
  }

  const linkText = await page.locator("a").allInnerTexts().then((items) => items.join("\n")).catch(() => "");
  const screenText = await page.locator("body").innerText();
  const sanitizedText = redactText(screenText);
  const observations = observationDraft(sanitizedText, redactText(linkText), finalActionText);

  const screenshotPath = path.join(outputDir, "final-screen-sanitized.png");
  const mask = page.locator("input[type='text'], input[type='email'], input[type='tel'], textarea");
  await page.screenshot({ path: screenshotPath, fullPage: true, mask: [mask], maskColor: "#000000" });
  await writeFile(path.join(outputDir, "final-screen-text-sanitized.txt"), `${sanitizedText}\n`, "utf8");

  const digest = await sha256(screenshotPath);
  const draftEvidence = {
    version: "ruby-woocommerce-final-confirmation-screen-evidence-v1",
    evidence_id: `capture-${new Date().toISOString().replace(/[:.]/g, "-")}`,
    environment: "preproduction",
    capture_method: "browser_screenshot_and_dom_notes",
    captured_at: new Date().toISOString(),
    source_url_class: "sanitized_preproduction_checkout",
    synthetic_customer_data_only: true,
    contains_personal_data: false,
    contains_secret_material: false,
    screen_capture_refs: [{
      artifact_ref: "artifact://sanitized/final-screen-sanitized.png",
      sha256: digest,
      redaction_applied: true,
      contains_personal_data: false,
      contains_secret_material: false,
    }],
    observations,
    authority: {
      order_creation_authorized: false,
      payment_execution_authorized: false,
      production_publish_authorized: false,
      catalog_mutation_authorized: false,
      dns_cutover_authorized: false,
    },
    review_notes: [
      "Automated preproduction capture draft only; observation booleans are heuristic and require evidence review before acceptance.",
      `Final action detected=${finalActionFound}; final action was not invoked.`,
    ],
    evidence_complete: false,
    actual_final_confirmation_screen_reviewed: false,
  };

  const captureSummary = {
    target_class: "ruby_woocommerce_preproduction",
    product_id_used_for_ephemeral_cart: product.id,
    final_action_found: finalActionFound,
    final_action_label: finalActionText,
    final_action_invoked: false,
    blocked_dangerous_request_count: blockedRequests.length,
    allowed_session_mutation_count: allowedSessionMutations.length,
    observations_detected_green: Object.values(observations).filter(Boolean).length,
    observations_total: Object.keys(observations).length,
    actual_screen_reviewed: false,
    payment_execution_authorized: false,
  };

  await writeFile(path.join(outputDir, "draft-evidence.json"), `${JSON.stringify(draftEvidence, null, 2)}\n`, "utf8");
  await writeFile(path.join(outputDir, "capture-summary.json"), `${JSON.stringify(captureSummary, null, 2)}\n`, "utf8");

  if (blockedRequests.length !== 0) {
    throw new Error(`safety guard blocked ${blockedRequests.length} dangerous request(s); capture rejected`);
  }
  if (!finalActionFound) throw new Error("final order action was not visible; capture is insufficient");

  console.log(
    `PHIL_AI_OS_RUBY_PREPRODUCTION_FINAL_SCREEN_CAPTURE_GREEN product=${product.id} ` +
    `observations=${captureSummary.observations_detected_green}/${captureSummary.observations_total} ` +
    "final_action_invoked=false order_creation=false payment_execution=false"
  );
} finally {
  await context.close();
  await browser.close();
}

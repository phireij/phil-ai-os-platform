# Phil AI OS Platform — Current Engineering Checkpoint

**Date:** 2026-09-11  
**Repository:** `phireij/phil-ai-os-platform`  
**Baseline main at checkpoint creation:** `3fd367ec9b331b7b6e188a697b7b8cd3a9ed097c`  
**Current merged main at this reconciliation:** `339b191b40170f64f5483ed744f8ebe244088a7d`

This is an additive current-state supplement to the canonical Master Executive Roadmap. It records gates that changed after the latest roadmap wording without changing sprint positioning or production authority.

## Sprint positioning

- **Sprint 3 — WooCommerce Foundation remains the CURRENT PRIMARY SPRINT.**
- **Sprint 4 — Customer Experience remains bounded parallel acceleration only.**
- The main Sprint 3 owner closure gate remains the final owner-approved production catalog/category/media source.
- No production cutover, live KOMOJU payment execution, unrestricted SMS sending, DNS switch, production catalog publication, or higher autonomy is authorized by this checkpoint.

## Twilio production callback — GREEN

The production Twilio delivery-status callback is deployed through the existing Control API at:

`https://hermes-agent-whow.srv1833510.hstgr.cloud/v1/webhooks/twilio/sms-status`

Verified production state:

- active image: `phil-ai-os/control-api:0.21.3-twilio-status-callback`
- exact HTTPS callback route converges through Traefik after Control API recreation
- unsigned callback is rejected with HTTP 403
- correctly signed but intentionally incomplete callback reaches application field validation and returns HTTP 400
- synthetic persistence was not used for HMAC verification
- callback persistence contract is redacted and non-authorizing
- no automatic retry is enabled
- no SMS was sent during deployment verification
- no WooCommerce, payment, DNS, or Mission Control mutation occurred

The observed ingress convergence behavior is expected and guarded: immediately after Control API recreation, the first unmatched callback probe may hit the existing Hermes catch-all route and return HTTP 302; the deployment workflow waits for the exact callback route to converge before evaluating HMAC readiness.

## Controlled outbound SMS readiness

The production SMS readiness candidate remains **disabled by default** and preserves these boundaries:

- provider: Twilio
- production sender identity: `RUBYSCAKE`
- production Messaging Service identity verified read-only
- Standard API key and Account SID/Auth Token credential paths verified for their intended read/authentication checks
- Account Auth Token remains the credential used for webhook HMAC validation
- bilingual transactional copy includes alternate help/opt-out contact
- support/opt-out contact: `order@rubyscakedelights.com`
- canonical production status callback configured
- automatic retry: false
- unrestricted send authority: false
- controlled handset test executed successfully: false

The combined no-send activation preflight is implemented and fail-closed. The approved test handset destination is already stored in GitHub Actions, provider identity and account binding checks are GREEN, and the Twilio account itself is verified `active` via a read-only Account resource diagnostic.

Twilio Support has now confirmed that the account is active, funded, has no account-level restrictions/compliance holds/risk flags preventing Messages API POST requests, and is authorized for Programmable Messaging SMS to Japan with the configured Alphanumeric Sender ID and Messaging Service.

PR #228 added a local/no-network support request inspector, and PR #229 added a manual GitHub Actions workflow that reconstructs the exact stored-secret request without sending any network request or SMS. The workflow completed GREEN using the stored production credential references and confirmed:

- Account SID shape and endpoint placement are valid;
- outbound Basic Auth uses the Standard API Key SID + API Key Secret;
- webhook Auth Token is not used for outbound authentication;
- `MessagingServiceSid` is used instead of `From`;
- the payload is form-encoded;
- no leading/trailing whitespace was detected in the stored credential/input values;
- the inspector itself performs no network transport and requested/sent no message.

Previous bounded diagnostics still show that Messages create/no-send POST authorization probes return HTTP 401 / Twilio `20003` even though non-create authentication checks succeed. The remaining issue is therefore still provider-side or provider-account/request-authority specific rather than an identified request-construction defect in Phil AI OS.

Until Twilio Support provides an actionable remediation, **no further controlled handset send attempts should be made**. The provider remains generally disabled, `automatic_retry=false`, and no broader SMS authority is granted.

## Sprint 4 CX hardening merged

The following bounded order-intake improvements are merged and remain local/network-inert:

- PR #198 — hidden custom-cake controls are disabled while Basic cake is selected, preventing hidden custom inputs/files from participating in validation or future form serialization while preserving reversible customer state.
- PR #199 — hidden Yamato time-window state is disabled for Ruby-car and shop-pickup modes while preserving the selection if the customer switches back to Yamato.
- PR #200 — requested-date section language is fulfillment-aware: delivery wording for Yamato/Ruby car and pickup wording for shop pickup.
- PR #201 — page-level notice and successful local preview status are also fulfillment-aware, removing delivery/shipping wording from the pickup path.
- PR #202 — requested pickup/delivery dates cannot be earlier than the current `Asia/Tokyo` calendar date; same-day requests remain allowed and the date floor is refreshed again at submit time.
- PR #204 — Shop pickup now captures a preferred pickup time without importing unconfirmed business-hour assumptions; the field is required only for pickup and disabled for other fulfillment modes.
- PR #205 — same-day Shop pickup rejects a preferred pickup time that is already in the past using Japan-local date/time only; no synthetic lead-time or opening-hours policy was introduced.

For these changes, Sprint 4 CX CI and Sprint 7 integrated readiness/runtime smoke gates were GREEN before merge. The preview still does not create orders, upload files, calculate live routes, charge payments, send SMS, mutate WooCommerce, publish customer content, change DNS, or expand production authority.

## Sprint 3 catalog handoff and controlled-review hardening merged

The owner-independent catalog path has been hardened before the Initial Launch Catalog V1 is supplied:

- PR #206 — catalog readiness now fails closed unless the intended initial-launch subset is explicitly complete and the canonical owner/source contract remains intact; JPY, bilingual/media provenance, draft/hidden intake state, and no-production-write handoff boundaries cannot be weakened.
- PR #207 — owner packages reject duplicate category and product slugs independently for both English and Japanese projections.
- PR #208 — read-only WooCommerce catalog snapshots reject duplicate product slugs, and planning blocks when an owner-desired product slug is already occupied by a different existing SKU.
- PR #209 — controlled-review product plans must remain `status=draft` and `catalog_visibility=hidden`, preventing publication-state drift after planning.
- PR #210 — controlled-review plans reject duplicate category action keys/slugs and duplicate product action SKUs/slugs.
- PR #211 — controlled-review plans reject negative, non-numeric, NaN, and infinite product prices; desired prices must remain finite non-negative decimal strings.
- PR #212 — controlled-review product actions reject duplicate `category_slugs` and `media_keys`, including whitespace-normalized duplicates.
- PR #226 — read-only WooCommerce catalog snapshots reject duplicate category references within a product and reject product category slugs that are absent from the snapshot category inventory.

These gates are validation/planning only. They do not perform WooCommerce network writes, create or publish products, delete existing products, execute payments, send SMS, change DNS, or grant mutation/execution/publication authority.

## Ambient shipping / smaller-box path — GREEN in pre-production contracts

Ruby's Cake Delights has approved smaller ambient-shipping support for products such as brownies and caramel bars.

Merged work:

- PR #231 — added a fail-closed ambient package-selection policy with `ambient_compact`, `ambient_60`, `ambient_80`, `ambient_100`, and `ambient_120` package classes. A SKU minimum is never downgraded; multi-unit/mixed Compact carts fall back to Size 60 unless physical packing evidence confirms Compact fit.
- PR #232 — added a manual production **read-only** WooCommerce shipping-zone/method snapshot workflow using existing read-only credentials. It uses GET only, stores no shipping `settings`, and cannot create/enable/price shipping methods.
- PR #235 — extended the canonical product schema with `ambient-compact`, `ambient-60`, `ambient-80`, `ambient-100`, `ambient-120` plus the `ambient` temperature mode.
- PR #236 — aligned the runtime fulfillment model with the same ambient shipping classes and added regression coverage.

Brownies and caramel bars are intended candidates for `ambient-compact`, subject to actual package-fit confirmation before their final catalog entries are approved. Live Hostinger/WooCommerce shipping-zone or rate mutation remains gated and has not been performed.

## Ruby catalog SKU convention — GREEN

PR #237 standardized the catalog authoring convention as:

`RCD-PRODUCT-FORM[-OPTION]`

Initial stable examples:

- `RCD-MCH-RD-15` = Ruby's Cake Delights / Moist Chocolate / Round / 15 cm
- `RCD-MCH-RD-21` = Ruby's Cake Delights / Moist Chocolate / Round / 21 cm
- `RCD-MCH-SQ-21` = Ruby's Cake Delights / Moist Chocolate / Square / 21 cm

Starting codes include `MCH = Moist Chocolate`, `RD = Round`, and `SQ = Square`. Customer-specific customization metadata (uploaded reference images, messages, colors, notes, etc.) is not encoded into the physical stock SKU unless Ruby intentionally sells it as a distinct stock-bearing variation.

A deterministic SKU builder/parser and tests are merged. This standard is for catalog authoring/validation only and does not publish or mutate products.

## AirREGI Quick Pickup / inventory bridge feasibility

PR #230 started the bounded parallel feasibility investigation for WooCommerce Quick Pickup while preserving AirREGI as the intended physical shop inventory authority.

Current conclusion:

- WooCommerce Quick Pickup remains feasible as a customer-facing product feature.
- AirREGI native inventory management is confirmed.
- AirREGI's public Data Integration API documentation still does **not** document product/inventory quantity endpoints for arbitrary custom merchant integrations; direct inventory API integration therefore remains **UNPROVEN / fail-closed**.
- PR #234 confirmed an official CSV fallback path: AirREGI can export current inventory for bulk editing and accept bulk inventory CSV updates, and its product-code field can intentionally align with external-system identifiers such as WooCommerce SKUs.

A controlled CSV bridge is therefore technically possible if a supported direct inventory API cannot be established, but it must include freshness/staleness limits, conservative availability, deterministic SKU mapping, reconciliation and explicit production authority before launch. UI scraping is not authorized.

## Current operational blockers / owner dependencies

1. **Primary Sprint 3 closure:** final owner-approved production catalog/category/media source (Initial Launch Catalog V1), including final product/variation SKUs and fulfillment/package classifications.
2. **Ambient shipping production configuration:** actual Compact/product fit confirmation and final Yamato/customer-facing rate matrix are still required before live shipping configuration is proposed.
3. **Controlled Twilio handset validation:** external dependency on Twilio Support to resolve Messages API POST authorization (`HTTP 401 / Twilio 20003`). No further send attempts should be made until Twilio provides actionable remediation.
4. **AirREGI direct inventory bridge:** endpoint-level direct inventory API capability remains unproven; CSV fallback is documented but no production synchronization path is authorized.

Owner-independent work should continue only where it materially improves the catalog/shipping handoff, read-only evidence, or integration feasibility. Do not manufacture micro-hardening simply to generate activity.

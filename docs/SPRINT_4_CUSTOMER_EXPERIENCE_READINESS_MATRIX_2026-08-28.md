# Sprint 4 — Customer Experience Readiness Matrix

Date: 2026-08-28
Status: GREEN / BOUNDED ENGINEERING CLOSURE READY

## Scope interpretation

This matrix evaluates the roadmap-defined Sprint 4 customer-experience engineering scope in an isolated/synthetic environment. It does **not** authorize production WooCommerce/KOMOJU connectivity, public-site cutover or live payment/order execution. Those remain separately governed activation/deployment concerns.

| Readiness area | Evidence | Result |
|---|---|---|
| Mobile-first shell | viewport baseline, responsive single/two/three-column layouts, 44px interaction targets, mobile-safe header/forms | GREEN |
| PWA foundation | standalone manifest, same-origin service worker, offline app shell, cache cleanup/versioning | GREEN |
| EN/JA customer experience | strict localized projection, locale switching, bilingual product/SEO/pickup/cart copy, missing translation fail-closed | GREEN |
| Catalog/product pages | synthetic catalog, product cards, product details, media alt-text, availability states | GREEN |
| SEO | preview `noindex,nofollow`, no preview canonical, explicit HTTPS requirement for later deployment canonical, localized product metadata/structured data | GREEN |
| Checkout intent | single/multi-item intent, quantity validation, duplicate-SKU rejection, pickup-only fulfillment, mutation authority false | GREEN |
| Cart pricing | deterministic line totals/cart total, JPY pilot, mixed-currency fail-closed | GREEN |
| Pickup | synthetic lead-time/max-advance policy, missing/too-soon/too-far negative paths, valid window path | GREEN |
| Inventory blocker | in-stock/out-of-stock states and readiness blocker behavior | GREEN |
| Customer-flow state | bounded state machine, invalid transition rejection, ready/blocked/error/recovery paths | GREEN |
| KOMOJU merchant architecture | provider fixed to KOMOJU, WooCommerce-plugin boundary, account-sign-in profile, connection not configured | GREEN |
| Payment handoff | only after GREEN checkout readiness; intent identity/amount/items/pickup retained; no external order claim | GREEN |
| Payment authority | order creation false; payment execution false; live mode false | GREEN |
| Credential safety | WooCommerce and KOMOJU credential-pattern scans; no merchant secrets present | GREEN |
| Cross-contract consistency | catalog → checkout → readiness → payment handoff continuity; deterministic 2-item ¥1,400 proof | GREEN |
| Accessibility baseline | landmarks, labels, skip links, focus-visible behavior, reduced-motion rule | GREEN |
| Empty/error/offline behavior | empty catalog state, load error state, same-origin offline shell fallback | GREEN |
| Isolated HTTP preview | catalog + cart page + fixtures/modules served and smoke-tested on loopback | GREEN |
| Production connectivity | intentionally absent | GATED / NOT REQUIRED FOR BOUNDED CLOSURE |
| Public site cutover | intentionally absent | GATED / SPRINT 7 / ACTIVATION WORK |
| KOMOJU Test/Live account connection | intentionally absent | GATED / LATER ACTIVATION |

## Automated evidence

Latest implementation validation before this matrix:

- GitHub Actions run: `33168942868`;
- validated head: `de4ae6adbc49ae2da09dc333de50a973b2a6a552`;
- unit tests: **36/36 GREEN**;
- CX/PWA/accessibility/safety validation: GREEN;
- cross-contract compatibility: GREEN;
- inert payment-handoff contract: GREEN;
- loopback HTTP smoke: GREEN.

Markers:

- `PHIL_AI_OS_SPRINT_4_CX_VALIDATION_GREEN`
- `PHIL_AI_OS_SPRINT_4_CX_CONTRACT_COMPATIBILITY_GREEN total_jpy=1400 items=2`
- `PHIL_AI_OS_SPRINT_4_PAYMENT_HANDOFF_CONTRACT_GREEN`

## Closure judgment

All roadmap-defined Sprint 4 engineering capabilities are represented and validated at the bounded foundation level:

1. mobile-first experience;
2. PWA;
3. SEO;
4. product pages;
5. checkout;
6. pickup;
7. bilingual customer experience.

The payment decision is also now incorporated safely: KOMOJU is modeled as the intended merchant through the WooCommerce integration boundary, without expanding production authority.

### Result

**SPRINT 4 BOUNDED CUSTOMER EXPERIENCE FOUNDATION: GREEN / READY TO CLOSE.**

Production activation remains explicitly outside this closure.

`PHIL_AI_OS_SPRINT_4_CUSTOMER_EXPERIENCE_READINESS_GREEN`

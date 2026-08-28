# Sprint 4 — Customer Experience Backlog

Date: 2026-08-28
Status: ACTIVE / EARLY ENTRY / SLICES 1–3 GREEN
Source: `docs/MASTER_EXECUTIVE_ROADMAP_SCHEDULE_CONTROL.md`

## Roadmap scope

Sprint 4 delivers:

1. mobile-first experience;
2. PWA;
3. SEO;
4. product pages;
5. checkout;
6. pickup;
7. bilingual English/Japanese customer experience.

Original roadmap window: **2026-09-08 to 2026-09-14**.

Sprint 3 closed GREEN early on 2026-08-28, so bounded Sprint 4 work began immediately.

## CX-1 — Contract-driven customer view models — GREEN

- catalog card projection;
- product-detail projection;
- deterministic EN/JA selection;
- currency display;
- stable customer-facing routes;
- synthetic/verified fixture boundary.

Evidence: missing translations fail closed and the projection layer is covered by automated tests.

## CX-2 — Mobile-first PWA foundation — GREEN

- responsive app shell;
- mobile navigation and touch targets;
- installable manifest;
- same-origin service-worker cache;
- reduced-motion/accessibility baseline;
- isolated HTTP smoke test.

Evidence: PWA/static checks and loopback-only HTTP smoke are GREEN.

## CX-3 — Product pages + SEO — GREEN FOUNDATION

- catalog/product page composition;
- localized title/description behavior;
- Product structured data;
- canonical-route policy;
- preview-vs-deployment search-indexing policy;
- media alt-text contract.

Evidence: preview defaults to `noindex,nofollow`; deployment canonical metadata requires explicit HTTPS configuration; EN/JA behavior is tested.

## CX-4 — Checkout + pickup + payment handoff — GREEN FOUNDATION

- single- and multi-item checkout intents;
- quantity and duplicate-SKU validation;
- deterministic JPY cart pricing;
- pickup-time intent;
- synthetic pickup-policy validation;
- readiness evaluation;
- unavailable-inventory/customer-action blocker paths;
- explicit non-authorizing state;
- KOMOJU selected as the intended payment merchant;
- KOMOJU integration modeled through the WooCommerce plugin boundary;
- inert KOMOJU payment-handoff intent with connection state `not_configured`;
- order creation, payment execution and live mode explicitly unauthorized.

Evidence: payment handoff is refused until checkout readiness is GREEN; mixed currency fails closed; secret-pattern safety checks cover WooCommerce and KOMOJU credential formats; no merchant secrets are present.

## CX-5 — Customer-flow QA — IN PROGRESS

Completed:

- customer-flow state machine;
- EN/JA projection tests;
- accessibility landmarks/labels baseline;
- unavailable/error/empty states;
- offline app-shell behavior;
- security/safety scan;
- isolated customer-flow smoke;
- payment-boundary negative-path tests.

Remaining before bounded Sprint 4 closure:

- true multi-item cart presentation in the isolated browser preview;
- visible inert KOMOJU handoff/readiness presentation;
- cross-schema/fixture compatibility validation;
- broader responsive/customer-flow acceptance matrix;
- final Sprint 4 readiness matrix and closure review.

## Current validation state

Pull-request run `33168460947`:

- **36/36 unit tests GREEN**;
- `PHIL_AI_OS_SPRINT_4_CX_VALIDATION_GREEN`;
- `PHIL_AI_OS_SPRINT_4_PAYMENT_HANDOFF_CONTRACT_GREEN`;
- loopback HTTP/PWA smoke GREEN;
- teardown GREEN.

Formal slice records:

- `docs/SPRINT_4_CUSTOMER_EXPERIENCE_SLICE_1_2026-08-28.md`
- `docs/SPRINT_4_CUSTOMER_EXPERIENCE_SLICE_2_2026-08-28.md`
- `docs/SPRINT_4_CUSTOMER_EXPERIENCE_SLICE_3_2026-08-28.md`

## Parallel work allowed

Operations Hub schemas/mocks/normalization may continue in parallel when they do not add external account access or live write capability.

## Authority boundary

Sprint 4 may build and test read-side/customer-intent/payment-handoff behavior in isolation. Any transition to a live store action, live order creation, KOMOJU account connection, Test/Live payment execution, production webhook, site cutover, new execution class, specialist execution, higher autonomy, or Mission Control write authority remains outside this bounded backlog and requires the applicable separately governed decision.

`PHIL_AI_OS_SPRINT_4_CUSTOMER_EXPERIENCE_BACKLOG_ACTIVE`

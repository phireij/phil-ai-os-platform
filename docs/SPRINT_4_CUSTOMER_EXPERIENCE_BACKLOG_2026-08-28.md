# Sprint 4 — Customer Experience Backlog

Date: 2026-08-28
Status: **CLOSED GREEN / COMPLETED EARLY**
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
Bounded engineering closure: **2026-08-28**.

## CX-1 — Contract-driven customer view models — GREEN

- catalog card projection;
- product-detail projection;
- deterministic EN/JA selection;
- currency display;
- stable customer-facing routes;
- synthetic/verified fixture boundary.

## CX-2 — Mobile-first PWA foundation — GREEN

- responsive app shell;
- mobile navigation and touch targets;
- installable manifest;
- same-origin service-worker cache;
- reduced-motion/accessibility baseline;
- isolated HTTP smoke test.

## CX-3 — Product pages + SEO — GREEN

- catalog/product page composition;
- localized title/description behavior;
- Product structured data;
- canonical-route policy;
- preview-vs-deployment search-indexing policy;
- media alt-text contract.

## CX-4 — Checkout + pickup + payment handoff — GREEN

- single- and multi-item checkout intents;
- quantity and duplicate-SKU validation;
- deterministic JPY cart pricing;
- pickup-time intent and synthetic policy validation;
- readiness/blocker behavior;
- isolated browser-visible multi-item cart;
- KOMOJU selected as intended payment merchant;
- WooCommerce-plugin KOMOJU integration boundary;
- inert KOMOJU payment-handoff intent;
- order creation, payment execution and live mode explicitly unauthorized.

## CX-5 — Customer-flow QA — GREEN

- customer-flow state machine;
- EN/JA projection tests;
- accessibility landmarks/labels/focus baseline;
- unavailable/error/empty states;
- offline app-shell behavior;
- credential/security/safety scans;
- isolated catalog/cart HTTP smoke;
- payment-boundary negative paths;
- cross-schema/fixture compatibility validation;
- deterministic 2-item ¥1,400 checkout/readiness/payment continuity proof;
- final Sprint 4 readiness matrix.

## Final validation state

Closure-matrix run `33169040068`:

- **36/36 unit tests GREEN**;
- `PHIL_AI_OS_SPRINT_4_CX_VALIDATION_GREEN`;
- `PHIL_AI_OS_SPRINT_4_CX_CONTRACT_COMPATIBILITY_GREEN total_jpy=1400 items=2`;
- `PHIL_AI_OS_SPRINT_4_PAYMENT_HANDOFF_CONTRACT_GREEN`;
- loopback catalog/cart/PWA smoke GREEN;
- teardown GREEN.

## Formal records

- `docs/SPRINT_4_CUSTOMER_EXPERIENCE_SLICE_1_2026-08-28.md`
- `docs/SPRINT_4_CUSTOMER_EXPERIENCE_SLICE_2_2026-08-28.md`
- `docs/SPRINT_4_CUSTOMER_EXPERIENCE_SLICE_3_2026-08-28.md`
- `docs/SPRINT_4_CUSTOMER_EXPERIENCE_SLICE_4_2026-08-28.md`
- `docs/SPRINT_4_CUSTOMER_EXPERIENCE_READINESS_MATRIX_2026-08-28.md`
- `docs/SPRINT_4_FORMAL_CLOSURE_2026-08-28.md`

## Authority boundary at closure

Sprint 4 closure is a bounded engineering closure only. Live store actions, live order creation, KOMOJU account connection, Test/Live payment execution, production webhooks, public-site/DNS cutover, new execution classes, specialist execution, higher autonomy and Mission Control write authority remain separately gated.

`PHIL_AI_OS_SPRINT_4_CUSTOMER_EXPERIENCE_BACKLOG_CLOSED_GREEN`

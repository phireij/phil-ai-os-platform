# Sprint 4 — Customer Experience Backlog

Date: 2026-08-28
Status: ACTIVE / EARLY ENTRY
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

Sprint 3 closed GREEN early on 2026-08-28, so bounded Sprint 4 work may begin immediately.

## CX-1 — Contract-driven customer view models

- catalog card projection;
- product-detail projection;
- deterministic EN/JA selection;
- currency display;
- stable customer-facing routes;
- synthetic/verified fixture boundary.

Exit: projection tests GREEN and missing translations fail closed.

## CX-2 — Mobile-first PWA foundation

- responsive app shell;
- mobile navigation and touch targets;
- installable manifest;
- same-origin service-worker cache;
- reduced-motion/accessibility baseline;
- isolated HTTP smoke test.

Exit: PWA/static checks GREEN on loopback-only preview.

## CX-3 — Product pages + SEO

- catalog/product page composition;
- localized title/description behavior;
- Product structured data;
- canonical-route policy;
- search-indexing policy for preview vs later live environment;
- media alt-text contract.

Exit: deterministic EN/JA product metadata and structured-data tests GREEN.

## CX-4 — Checkout + pickup intent

- quantity selection;
- pickup-time intent;
- readiness evaluation;
- unavailable-inventory path;
- customer-action blockers;
- explicit non-authorizing state.

Exit: checkout/readiness remains contract-driven and does not create a live order.

## CX-5 — Customer-flow QA

- responsive-state checks;
- EN/JA parity;
- accessibility landmarks/labels/focus behavior;
- unavailable/error/empty states;
- offline app-shell behavior;
- security/safety scan;
- isolated customer-flow smoke.

Exit: bounded Sprint 4 readiness matrix GREEN.

## Parallel work allowed

Operations Hub schemas/mocks/normalization may continue in parallel when they do not add external account access or live write capability.

## Authority boundary

Sprint 4 may build and test read-side/customer-intent behavior in isolation. Any transition to a live store action, live order creation, payment execution, site cutover, new execution class, specialist execution, higher autonomy, or Mission Control write authority remains outside this bounded backlog and requires a separately governed decision.

`PHIL_AI_OS_SPRINT_4_CUSTOMER_EXPERIENCE_BACKLOG_ACTIVE`

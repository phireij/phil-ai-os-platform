# Sprint 7 — Launch Acceptance Matrix

Date: 2026-08-29
Status: ENGINEERING READINESS PACKAGE / LIVE LAUNCH NOT AUTHORIZED

## Acceptance principle

Sprint 7 separates **bounded engineering readiness** from **live production authorization**. Engineering can remain GREEN while live launch is blocked by WordPress/WooCommerce pre-production QA, fresh recovery checks, production payment/shipping configuration and explicit activation sign-off.

## Current matrix

| Gate | Current state | Launch effect |
|---|---|---|
| Integrated regression baseline | **165-test baseline proven GREEN in Sprint 7 Slice 1**; final branch head must also be GREEN before merge/closure. | Required engineering gate. |
| Isolated WooCommerce + CX runtime smoke | GREEN at Slice 1; must remain GREEN at final head. | Required engineering gate. |
| Security/recovery package | **READY**; historical Phase 1.17 backup/restore proof exists. | Fresh launch-time backup/restore recheck remains required. |
| Replay/idempotency/authority controls | **GREEN** in bounded regression. | Must remain GREEN through launch. |
| Production secret handling | **PLAN READY / NO PRODUCTION PAYMENT AUTHORITY AUTHORIZED**. | Block live integration until approved. |
| WooCommerce deployment runbook | **READY / PARALLEL PRE-PRODUCTION FIRST**. | Public cutover remains blocked pending pre-production QA, fresh recovery proof and approval. |
| Ruby business profile | **COMPLETE — 15/15 RESOLVED**. | Business-profile content verification blocker closed; publication remains separately gated. |
| Contact phone | **VERIFIED — 050-1785-0575**. | Phone verification gate complete. |
| Tokushoho source | **RECONCILED / PUBLICATION APPROVAL PENDING**. | Legal source-reconciliation blocker closed; final checkout/payment/shipping sync and CEO publication approval still required. |
| Old builder products/categories | **EXCLUDED / NOT AUTHORITATIVE**. | Must not be migrated as production catalog. |
| WooCommerce pre-production QA | **NOT YET GREEN**. | Current primary storefront-preparation blocker. |
| Hostinger native WordPress staging | Requires an existing detected WordPress installation and eligible hosting plan; **eligibility/use not yet verified for Ruby**. | Native staging is a later convenience layer, not the first migration step from Website Builder. |
| WooCommerce production identity/credentials | **NOT AUTHORIZED / NOT CONFIGURED**. | Blocks live API integration. |
| KOMOJU Test Mode | **NOT VALIDATED**. | Must be configured and tested only after the separate Test Mode gate is approved. |
| KOMOJU Live Mode | **NOT AUTHORIZED**. | Blocks real payment launch. |
| Shipping configuration | Legacy Yamato Cool terms captured; **production configuration/rates not yet verified**. | Must match WooCommerce checkout and Tokushoho before launch. |
| Payment methods | Legacy card brands captured; **actual merchant-available/production-enabled methods not yet verified**. | Must match KOMOJU merchant account, WooCommerce checkout and Tokushoho. |
| External channel activation | Runbooks READY; live identities/connectivity/replies remain disabled. | Does not block storefront-only launch unless channels are explicitly in launch scope. |
| Operator quick-start / incident handling | **READY**. | Required documentation gate. |
| CEO sign-off | **NOT RECORDED**. | Blocks live launch. |
| CTO sign-off | **NOT RECORDED**. | Blocks live launch. |

## Launch categories

### A. Bounded engineering acceptance

Can remain GREEN when:

- final branch CI is GREEN;
- all Sprint 7 readiness validators are GREEN;
- isolated runtime smoke is GREEN;
- no production credentials/secrets were introduced;
- no authority baseline drift occurred;
- readiness/runbook documentation is complete.

### B. Storefront pre-production acceptance

The business-profile prerequisite is now complete.

Because the current public Ruby site is **Hostinger Website Builder**, not WordPress, Hostinger's native WordPress staging tool cannot be the initial migration environment. Current Hostinger guidance requires an existing WordPress installation to be detected before native WordPress staging can be created.

The next storefront gate therefore requires:

- create a **separate non-public Hostinger WordPress + WooCommerce pre-production site** without moving `rubyscakedelights.shop`;
- keep the current Website Builder storefront serving customers;
- verify whether Ruby's Hostinger plan supports native WordPress staging after WordPress exists;
- load verified profile/policies into pre-production;
- create approved production product/category source data independently of the old test catalog;
- configure and test both store pickup and intended Yamato Cool delivery behavior;
- SSL, cart, checkout, mobile, bilingual and accessibility QA GREEN;
- reconcile production shipping zones/rates with customer-facing legal disclosure;
- no public domain/DNS cutover yet.

### C. Payment acceptance

Requires:

- WooCommerce pre-production readiness;
- official KOMOJU Payments WooCommerce plugin installed in the approved non-public context;
- KOMOJU account connected using the current sign-in/OAuth-style flow in **Test Mode** only after separate authorization;
- merchant-available payment methods verified and selected deliberately;
- controlled Test Mode transactions GREEN, including order-state correlation and failure/cancel behavior;
- customer-facing payment methods/timing synchronized with checkout and Tokushoho;
- merchant Live Mode approval verified;
- explicit CEO approval before Live Mode;
- successful narrow real-payment verification only after that later gate;
- disable/reconciliation path available.

### D. Recovery and cutover acceptance

Requires:

- fresh launch-time backup/restore verification;
- pre-production acceptance GREEN;
- legal/payment/shipping text synchronized with actual configuration;
- rollback path verified;
- explicit production cutover authorization;
- CEO and CTO sign-off.

### E. Channel acceptance

For each channel in launch scope:

- current platform capability/permissions verified;
- approved identity and least-privilege credentials;
- read-only canary GREEN;
- authenticity/idempotency/governance checks GREEN;
- disable/revoke path GREEN;
- separate outbound reply/write approval if required.

## Current launch conclusion

**Bounded Sprint 7 engineering remains GREEN and the Verified Ruby Business Profile is complete. Live launch is still not authorized.** The primary remaining storefront/payment blockers are creation and QA of the parallel Hostinger WordPress/WooCommerce pre-production site, production shipping configuration/rate verification, KOMOJU Test Mode validation and payment-method verification, fresh launch-time backup/restore proof, final Tokushoho publication approval, and CEO/CTO sign-off.

## Sign-off record template

Record only after all launch-scope gates are satisfied:

- Launch scope:
- Target date/time:
- Final CI head:
- Backup/restore verification:
- Storefront pre-production acceptance:
- Shipping configuration/rates verification:
- WooCommerce production activation decision:
- KOMOJU Test/Live decision:
- Payment methods verified:
- Tokushoho publication approval:
- External channel scope:
- Rollback owner/path:
- CEO sign-off:
- CTO sign-off:
- Go / No-Go decision:

`PHIL_AI_OS_SPRINT_7_LAUNCH_ACCEPTANCE_PACKAGE_READY_NOT_SIGNED`

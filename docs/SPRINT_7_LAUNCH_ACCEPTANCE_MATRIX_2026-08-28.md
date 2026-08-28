# Sprint 7 — Launch Acceptance Matrix

Date: 2026-08-28
Status: ENGINEERING READINESS PACKAGE / LIVE LAUNCH NOT AUTHORIZED

## Acceptance principle

Sprint 7 separates **bounded engineering readiness** from **live production authorization**. Engineering can close GREEN while live launch remains blocked by business-data verification, fresh recovery checks, production identities/credentials and explicit activation sign-off.

## Current matrix

| Gate | Current state | Launch effect |
|---|---|---|
| Integrated regression baseline | **165-test baseline proven GREEN in Sprint 7 Slice 1**; final branch head must also be GREEN before merge/closure. | Required engineering gate. |
| Isolated WooCommerce + CX runtime smoke | GREEN at Slice 1; must remain GREEN at final head. | Required engineering gate. |
| Security/recovery package | **READY**; historical Phase 1.17 backup/restore proof exists. | Fresh launch-time backup/restore recheck remains required. |
| Replay/idempotency/authority controls | **GREEN** in bounded regression. | Must remain GREEN through launch. |
| Production secret handling | **PLAN READY / NO PRODUCTION SECRETS AUTHORIZED**. | Block live integration until approved. |
| WooCommerce deployment runbook | **READY / STAGING-FIRST**. | Production cutover blocked pending verified data, fresh recovery proof and approval. |
| Ruby business profile | **INCOMPLETE**. | **BLOCKS production content/cutover.** |
| Contact phone | **UNVERIFIED**. | **BLOCKS publication of the old phone value.** |
| Old builder products/categories | **EXCLUDED / NOT AUTHORITATIVE**. | Must not be migrated as production catalog. |
| WooCommerce production identity/credentials | **NOT AUTHORIZED / NOT CONFIGURED by Sprint 7 package**. | Blocks live API integration. |
| KOMOJU integration | `not_configured`; Test Mode and Live Mode not authorized by the readiness package. | Blocks real payment launch until separately approved/validated. |
| External channel activation | Runbooks READY; live identities/connectivity/replies remain disabled. | Does not block storefront-only launch unless channels are explicitly in launch scope. |
| Operator quick-start / incident handling | **READY**. | Required documentation gate. |
| CEO sign-off | **NOT RECORDED**. | Blocks live launch. |
| CTO sign-off | **NOT RECORDED**. | Blocks live launch. |

## Launch categories

### A. Bounded engineering acceptance

Can be marked GREEN when:

- final branch CI is GREEN;
- all Sprint 7 readiness validators are GREEN;
- isolated runtime smoke is GREEN;
- no production credentials/secrets were introduced;
- no authority baseline drift occurred;
- readiness/runbook documentation is complete.

### B. Storefront production acceptance

Requires additional evidence not supplied by bounded engineering alone:

- verified Ruby Business Profile;
- verified contact phone;
- approved production catalog/category source data;
- Hostinger WordPress/WooCommerce staging QA;
- SSL and checkout/pickup QA;
- fresh pre-cutover backup/restore proof;
- explicit production cutover authorization;
- successful narrow launch/cutover checks.

### C. Payment acceptance

Requires:

- WooCommerce storefront readiness;
- KOMOJU Test Mode approval/configuration and GREEN test evidence;
- merchant production readiness;
- explicit Live Mode approval;
- successful narrow real-payment verification when authorized;
- reconciliation and disable/rollback path.

### D. Channel acceptance

For each channel in launch scope:

- current platform capability/permissions verified;
- approved identity and least-privilege credentials;
- read-only canary GREEN;
- authenticity/idempotency/governance checks GREEN;
- disable/revoke path GREEN;
- separate outbound reply/write approval if required.

## Current launch conclusion

**Bounded Sprint 7 engineering is progressing, but live launch is not yet authorized.** The most important known live-launch blockers are the incomplete verified Ruby Business Profile, unverified phone value, fresh launch-time backup/restore recheck, production WooCommerce/KOMOJU activation decisions and final CEO/CTO sign-off.

## Sign-off record template

Record only after all launch-scope gates are satisfied:

- Launch scope:
- Target date/time:
- Final CI head:
- Backup/restore verification:
- Storefront staging acceptance:
- WooCommerce production activation decision:
- KOMOJU Test/Live decision:
- External channel scope:
- Rollback owner/path:
- CEO sign-off:
- CTO sign-off:
- Go / No-Go decision:

`PHIL_AI_OS_SPRINT_7_LAUNCH_ACCEPTANCE_PACKAGE_READY_NOT_SIGNED`

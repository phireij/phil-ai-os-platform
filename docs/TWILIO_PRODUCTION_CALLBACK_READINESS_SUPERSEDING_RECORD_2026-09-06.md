# Twilio Production Callback Readiness — Superseding Record

**Date:** 6 September 2026  
**Scope:** Ruby’s Cake Delights transactional SMS delivery-status callback  
**Authority:** readiness evidence only; this record does **not** authorize unrestricted SMS, retries, WooCommerce mutation, payment execution, DNS cutover, Mission Control mutation, higher autonomy, or final Go/No-Go.

## Status

**PRODUCTION DELIVERY-STATUS CALLBACK: GREEN**

This record supersedes earlier readiness notes that described the public Twilio delivery-status callback as pending deployment/verification. It does not modify or replace any sensitive v2 production-authorization gate.

## Verified evidence

- Existing Twilio Production Read-Only Preflight is GREEN with `confirm_no_send=true`.
- Paid Ruby-owned Twilio account, `Ruby Transactional SMS` Messaging Service and `RUBYSCAKE` Japan Alphanumeric Sender remain the intended production identities.
- Outbound REST authentication remains separated from webhook authentication:
  - outbound REST: restricted API key SID/secret;
  - webhook signature validation: Account Auth Token.
- Production callback is deployed into the existing Control API, not a parallel ad-hoc service.
- Active Control API callback image: `phil-ai-os/control-api:0.21.3-twilio-status-callback`.
- Canonical HTTPS callback path: `/v1/webhooks/twilio/sms-status` on the existing `hermes-agent-whow.srv1833510.hstgr.cloud` HTTPS host.
- No DNS/public cutover was performed.
- Traefik uses an exact `POST` callback router with higher priority than the catch-all Hermes host router.
- Initial public request immediately after container recreation reached the existing Hermes catch-all and returned HTTP 302; bounded router-convergence verification then observed the exact callback route on the second probe and received HTTP 403 for an unsigned callback.
- A correctly signed but intentionally incomplete callback returned HTTP 400, proving that the canonical external URL plus Account Auth Token HMAC validation reached application field validation without persisting a synthetic delivery event.
- Callback parser remains bounded to 8 KiB `application/x-www-form-urlencoded`, rejects malformed/duplicate fields, and fails closed on missing/invalid signatures.
- Delivery-status persistence is redacted/non-authorizing: Message SID is stored only as a short SHA-256 hash projection; status/error metadata is retained; `authority_effect='none'`; `retry_requested=0`.
- No automatic SMS retry path was enabled.
- No SMS was sent during deployment or verification.
- Final deployment workflow `Control API Twilio Status Callback Deploy`, run `34005653649`, completed GREEN.
- Final deployment verification emitted `PHIL_AI_OS_TWILIO_STATUS_CALLBACK_DEPLOY_GREEN` with:
  - `sms_send=false`
  - `automatic_retry=false`
  - `woo_mutation=false`
  - `payment_mutation=false`
  - `dns_mutation=false`
  - `mission_control_mutation=false`

## Supporting remediation evidence

During governed deployment, two fail-closed issues were found and repaired before final activation:

1. The generic `/v1/*` authorization guard appears in more than one request handler. The patch was narrowed to `do_POST` only rather than guessing an anchor.
2. The Control API secrets directory was `root:root` mode `0750`, preventing the UID/GID 10001 runtime user from traversing the bind mount. The parent directory was repaired to `root:10001` mode `0750`; existing Hermes Control API token authentication, Mission Control password readability and Control API health were verified without logging secret values.

All failed deployment attempts automatically restored the prior healthy `0.21.2-phase23p5` image before the final GREEN deployment.

## Remaining Twilio activation gates

This callback readiness milestone does **not** by itself authorize the CEO-approved controlled handset SMS test. Before that single test executes, the independent outbound-message readiness gates must still be GREEN, including the production bilingual template/help/opt-out contact requirement appropriate for a one-way Alphanumeric Sender ID.

Unrestricted SMS sending and automatic SMS retries remain prohibited.

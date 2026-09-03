# SMS Provider Decision Package — Japan — 2026-09-03

**Program:** Phil AI OS Platform / Ruby's Cake Delights  
**Use case:** Transactional payment-link fallback after Ruby approves an advance order  
**Current authority:** CEO has formally selected **Twilio** as the production SMS provider. Provider/account activation and live sending remain separately gated and fail-closed.

## Executive decision

**Twilio SMS is the formally selected production SMS provider for Ruby's Cake Delights.**

CEO selection date: **2026-09-03**.

Selection does not authorize a live send. Before production sending can become ready, Ruby must have an authorized Twilio account/integration identity, credentials must be stored in the approved secret boundary, Japan sender identity requirements must be verified for the exact account/use case, the bilingual message template must be approved, delivery-status webhook verification must pass, and a controlled recipient/handset test must demonstrate successful receipt and a usable payment link.

**AWS End User Messaging SMS** remains the documented secondary/fallback candidate if Ruby later needs a provider change or broader infrastructure consolidation.

## Why Twilio was selected

1. Japan-specific public pricing is straightforward for the small transactional volume expected during the pilot.
2. Twilio supports outbound Japan SMS and sender identity options suitable for a one-way transactional notification path.
3. Pay-as-you-go billing fits a low-volume pilot without requiring dedicated short-code infrastructure.
4. Twilio's delivery-status/callback model maps cleanly to the Phil AI OS provider-neutral SMS adapter and idempotent approval-payment notification flow.
5. It gives Ruby a practical path to validate real customer deliverability before considering a future provider change.

## Twilio — Japan planning facts

The provider research reviewed during selection found public Japan per-segment pricing and multiple sender/origination options. Pricing, carrier fees, identity support and registration requirements can change, so the exact commercial and sender configuration must be re-verified in the Ruby-owned Twilio account at activation time.

For Ruby's pilot, use the simplest compliant one-way transactional identity supported for the account and Japan destination traffic. Do not assume sender presentation or deliverability until the controlled handset test is GREEN.

## Provider-fit record

| Criterion | Twilio | AWS End User Messaging SMS |
|---|---|---|
| Japan outbound SMS | Supported | Supported |
| Low-volume pilot fit | **Strong** | Good |
| Webhook/status integration | Strong | Strong |
| Provider-neutral adapter fit | Strong | Strong |
| Current role | **FORMALLY SELECTED** | Secondary/fallback candidate |

## Proposed production message pattern

Keep the SMS short to minimize segmentation and make the customer action obvious.

Conceptual content only:

`Ruby's Cake Delights: Your order is confirmed. Please complete payment here: <secure WooCommerce payment link>`

Japanese/bilingual wording must be tested for segment count and readability before production. The message must not contain card data or other sensitive payment information; the only payment artifact is the HTTPS WooCommerce order-payment URL.

## Integration contract

The existing merged scaffold enforces:

- only orders in `pending` (approved and payment required) can trigger the payment-link SMS;
- no SMS while an order is still `waiting` for approval;
- no SMS for cancelled, failed, processing, completed or refunded orders;
- Japanese phone normalization;
- deterministic idempotency;
- duplicate suppression;
- safe payment-link redaction from normal audit output;
- fail-closed provider errors;
- no automatic retry;
- disabled external provider by default.

The Twilio adapter must implement this contract rather than bypass it.

## Remaining production activation gate

Before any live SMS is sent:

1. **GREEN — CEO formally selected Twilio.**
2. Create/verify the provider account/integration identity under Ruby's authorized business ownership.
3. Store credentials in the approved secret boundary; never in GitHub files, chat, or WordPress content.
4. Confirm Japan sender identity/registration requirements for the exact account and transactional use case.
5. Approve the final bilingual transactional message template.
6. Confirm durable idempotency and delivery-status audit persistence.
7. Verify Twilio status-webhook signature handling and delivery-state mapping.
8. Run a controlled test only to an approved recipient number.
9. Verify successful handset receipt and a usable WooCommerce payment link.
10. Only after all acceptance checks are GREEN may production notification sending be marked ready.

## Cost-control principle

SMS is a **fallback/companion transactional channel**, not a marketing channel. Send only the minimum notification needed after approval. No automatic repeated sends are permitted in V1; any resend/retry policy must be explicitly designed to prevent duplicate messages and unnecessary cost.

## Decision state

- Architecture: **READY**.
- Provider comparison: **COMPLETE**.
- Selected provider: **TWILIO — CEO APPROVED 2026-09-03**.
- Provider account/integration identity: **PENDING VERIFICATION/SETUP**.
- Credentials in approved secret boundary: **PENDING**.
- Japan sender identity: **PENDING VERIFICATION**.
- Controlled handset test: **PENDING**.
- Production sending readiness: **FALSE**.
- Live SMS: **DISABLED**.

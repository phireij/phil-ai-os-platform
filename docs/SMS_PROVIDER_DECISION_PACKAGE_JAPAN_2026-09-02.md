# SMS Provider Decision Package — Japan — 2026-09-02

**Program:** Phil AI OS Platform / Ruby's Cake Delights  
**Use case:** Transactional payment-link fallback after Ruby approves an advance order  
**Current authority:** Research/design only; no provider account, credentials, sender identity or live sending authorized

## Executive recommendation

For the **initial Ruby pilot**, prefer **Twilio SMS** as the first provider candidate, subject to a later explicit CEO activation gate.

Reasons:

1. Japan-specific public pricing is straightforward and transparent for the small transactional volume expected during the pilot.
2. Twilio supports outbound Japan SMS using short codes, long codes and alphanumeric Sender IDs, giving us a practical one-way branded-notification path.
3. Pay-as-you-go billing fits a low-volume pilot without committing to a dedicated short code.
4. Twilio's delivery status/callback model maps cleanly to the Phil AI OS provider-neutral SMS adapter and our idempotent approval-payment notification flow.
5. It lets us validate real customer deliverability before deciding whether SMS volume or broader infrastructure economics justify moving to another provider.

**AWS End User Messaging SMS** remains the preferred secondary candidate if we later want deeper AWS consolidation or higher-scale messaging operations. AWS officially supports SMS delivery to Japan, Sender IDs, two-way SMS, and international sending, but its broader origination/registration model is more infrastructure-heavy for Ruby's immediate low-volume fallback use case.

No provider is activated by this recommendation.

## Twilio — current Japan facts

Twilio's current Japan pricing page lists outbound SMS per segment as:

- Short code: **US$0.0800**;
- Long code: **US$0.0890**;
- Alphanumeric Sender ID: **US$0.089**.

Twilio notes that pricing is per message segment, can change, and additional carrier fees may apply. Its Japanese pricing page also states a **US$0.001** processing fee for messages that finish in `Failed` status.

For Ruby's use case, the initial implementation should favor the simplest supported **one-way transactional identity** rather than leasing a dedicated short code. Final sender-ID behavior and deliverability must be confirmed during controlled account-side testing because carrier presentation can vary.

Official source reviewed: `https://www.twilio.com/en-us/sms/pricing/jp` and the Japanese equivalent.

## AWS End User Messaging SMS — current Japan facts

AWS documents Japan (`JP`, dialing code `81`) as supporting:

- short codes;
- Sender IDs;
- two-way SMS;
- international sending.

AWS documents Sender IDs as branded alphanumeric identities and notes that country-specific requirements and registration behavior can apply. AWS also lists a Japan dedicated short code as a high-cost/high-commitment option (currently a one-time setup fee plus substantial monthly fee), which is unnecessary for Ruby's pilot volume.

Official sources reviewed:

- AWS supported countries/regions for SMS;
- AWS Sender ID documentation;
- AWS End User Messaging pricing documentation.

## Provider-fit comparison

| Criterion | Twilio | AWS End User Messaging SMS |
|---|---|---|
| Japan outbound SMS | Supported | Supported |
| Japan Sender ID | Supported | Supported |
| Two-way Japan SMS | Available depending on identity | AWS documents Japan as supported |
| Low-volume pilot fit | **Strong** | Good |
| Public Japan per-segment pricing clarity | **Strong** | More complex/route-dependent |
| Dedicated infrastructure required for pilot | No | No, but origination model is broader |
| Webhook/status integration | Strong | Strong |
| Pay-as-you-go pilot simplicity | **Strong** | Strong but more AWS-oriented setup |
| Fit with current provider-neutral scaffold | Strong | Strong |
| Current recommendation | **Primary pilot candidate** | Secondary candidate |

## Proposed production message pattern

Keep the SMS short to minimize segmentation and make the customer action obvious.

Conceptual content only:

`Ruby's Cake Delights: Your order is confirmed. Please complete payment here: <secure WooCommerce payment link>`

Japanese/bilingual wording should be tested for segment count and readability before production. The message must not contain card data or other sensitive payment information; the only payment artifact is the HTTPS WooCommerce order-payment URL.

## Integration contract

The existing merged scaffold already enforces:

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

A Twilio or AWS adapter must implement this contract rather than bypass it.

## Production activation gate

Before any live SMS is sent:

1. CEO explicitly approves the selected provider.
2. Create the provider account/integration identity under Ruby's authorized business ownership.
3. Store credentials in the approved secret boundary; never in GitHub files or WordPress content.
4. Confirm Japan sender identity/registration requirements for the exact account and use case.
5. Approve the final bilingual message template.
6. Add durable idempotency and delivery-status audit persistence.
7. Implement status webhook verification.
8. Run controlled tests only to CEO-approved recipient numbers.
9. Measure Inbox-equivalent customer outcome: successful handset receipt and usable payment link.
10. Only then authorize production notification sending.

## Cost-control principle

SMS is a **fallback/companion transactional channel**, not a marketing channel. Send at most the minimum notification needed after approval. No automatic repeated sends are permitted in V1; any resend/retry policy must be explicitly designed to prevent duplicate customer messages and unnecessary cost.

## Decision state

- Architecture: **READY**.
- Provider comparison: **READY**.
- Preferred pilot candidate: **TWILIO**.
- Provider account: **NOT CREATED / NOT AUTHORIZED**.
- Credentials: **NONE**.
- Live SMS: **DISABLED**.
- CEO activation gate: **REQUIRED LATER**.

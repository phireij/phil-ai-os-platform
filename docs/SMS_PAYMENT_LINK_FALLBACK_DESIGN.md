# SMS Payment-Link Fallback — Bounded Design

Status: **Pre-production scaffold only**  
Production provider: **Not selected / not authorized**  
Production sending: **Disabled**

## Purpose

Ruby's Cake Delights uses approval-before-payment for advance orders. After Ruby confirms the requested delivery/pickup date, WooCommerce moves the order from `waiting` to `pending` and SG Order Approval generates the customer payment URL.

Authenticated SMTP was validated with SPF, DKIM and DMARC passing, but Gmail classified both a diagnostic message and the real SG approval/payment-link email as Spam. Email therefore remains useful but cannot be the only customer notification channel.

The target customer flow is:

`Order submitted → Ruby confirms → order approved/pending payment → email payment link + SMS payment link → customer pays via KOMOJU`

## Authority boundary

This module does **not**:

- approve or reject an order;
- change an order status;
- charge, authorize, capture or refund a payment;
- enable KOMOJU Live Mode;
- select or activate a production SMS provider;
- create a production provider identity or credentials;
- automatically retry failed SMS sends;
- introduce a new Phil AI OS execution task class.

Production SMS activation remains a separate CEO approval gate.

## Eligibility contract

An SMS payment link may be prepared/sent only when the WooCommerce order is already in `pending` status (approved and payment required).

Never send for:

- `waiting` — still awaiting Ruby approval;
- `cancelled` / `failed` — no payment should be requested;
- `processing` / `completed` — payment/order has progressed;
- `refunded` — payment was reversed.

## Payload

The provider-neutral request contains:

- order ID and order number;
- order status;
- normalized customer phone;
- amount and currency;
- WooCommerce HTTPS payment URL;
- requested delivery/pickup date when available.

The full payment URL is allowed only inside the outbound notification payload. General audit output removes its query string/order key and masks the phone number.

## Idempotency

A deterministic SHA-256 idempotency key is derived from the notification type, order, eligible status, normalized phone and payment URL. The service suppresses duplicate sends within the active store and a future durable adapter must persist the same key before production activation.

## Failure behavior

Provider failures fail closed. There is **no automatic retry** in the scaffold. A future retry policy requires explicit bounded design and must avoid duplicate customer payment messages.

## Current adapters

- `DisabledSmsProvider` — default; never contacts an external service.
- `MemorySmsProvider` — isolated tests/pre-production contract validation only.

No live provider SDK, API key, sender identity or production endpoint is present.

## Required gate before live SMS

Before activation:

1. compare Japan-capable transactional SMS providers for delivery, sender behavior, cost and compliance;
2. select a provider;
3. approve the production integration identity/credentials;
4. add durable idempotency/audit storage;
5. validate Japanese mobile-number formatting and message templates;
6. run controlled test-recipient QA;
7. obtain explicit CEO authorization for production sending.

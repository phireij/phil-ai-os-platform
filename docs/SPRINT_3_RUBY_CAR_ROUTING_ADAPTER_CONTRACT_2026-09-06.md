# Sprint 3 — Ruby Car Routing Adapter Contract

Date: 2026-09-06
Status: PRE-PRODUCTION / NETWORK-INERT

## Purpose

Provide a bounded, read-only route-computation boundary that can later be implemented by Google Routes (or another approved routing provider) without changing the CEO-approved Ruby car delivery policy.

## Safety boundary

- The adapter is disabled by default.
- No concrete network transport or API key integration is included.
- The module cannot make a live Google Routes request by itself.
- An enabled adapter requires an explicitly injected transport.
- At most one route-computation call is made; there is no retry loop.
- Destinations outside Chiba, Tokyo, Kanagawa, and Saitama are rejected before any route call.
- The fixed origin remains `ruby_shop_ichikawa`.
- Customer destination addresses are excluded from the safe audit projection.
- Route facts do not authorize order mutation, payment, delivery confirmation, or vehicle dispatch.

## Contract flow

1. Validate a one-way request from the fixed Ruby shop origin.
2. Fail closed while provider activation is disabled.
3. Short-circuit destinations outside the approved service prefectures.
4. If separately enabled and supplied an injected provider transport, obtain one read-only route observation.
5. Normalize only distance, duration, toll expectation/price, and exceptional-parking facts.
6. Pass normalized facts to the existing `RubyCarDeliveryPolicy` for a provisional quote or manual-review decision.
7. Preserve `payment_authorized=false`, `order_mutation_authorized=false`, and `dispatch_authorized=false`.

## Production work deliberately deferred

The following remain separate future readiness-gated work:

- Google Routes project/API enablement and credential boundary;
- exact provider request/response mapping;
- live route preflight;
- runtime secret configuration;
- production route calls;
- customer-facing quote publication;
- dispatch workflow or driver assignment;
- any WooCommerce/order/payment mutation.

This contract therefore prepares the integration seam without expanding production authority.

# Sprint 3 — Google Routes Network-Inert Contract

Date: 2026-09-06
Status: CONTRACT-ONLY / NO LIVE API

## Purpose

Define the minimal Google Routes `computeRoutes` request/response mapping needed by the already merged Ruby car routing adapter, without adding credentials, HTTP transport, runtime wiring, or production activation.

## Provider contract captured

Official Google Routes documentation reviewed on 2026-09-06 confirms:

- Compute Routes uses `https://routes.googleapis.com/directions/v2:computeRoutes`.
- A response field mask is required; `X-Goog-FieldMask` is supported.
- Route-level `routes.distanceMeters` and `routes.duration` provide the distance/time facts needed by Ruby car policy.
- Toll computation is requested with `extraComputations: ["TOLLS"]` and returned under `routes.travelAdvisory.tollInfo` when available.
- Toll `estimatedPrice` uses Google Money values (`currencyCode`, `units`, optional `nanos`).

References:
- https://developers.google.com/maps/documentation/routes/compute_route_directions
- https://developers.google.com/maps/documentation/routes/choose_fields
- https://developers.google.com/maps/documentation/routes/calculate_toll_fees

## Implemented boundary

`google_routes_contract.py` only:

1. Builds a deterministic driving request body with traffic-aware routing, metric units, toll computation, no alternatives, and no avoid-toll/highway/ferry preference.
2. Exposes the fixed minimal field mask:
   `routes.distanceMeters,routes.duration,routes.travelAdvisory.tollInfo`.
3. Normalizes exactly one returned route into provider-neutral distance/duration/toll observation fields.
4. Rounds fractional duration seconds upward conservatively.
5. Treats toll information without a single usable JPY price as `tolls_expected=true` and `toll_yen=null`, which causes the existing Ruby car delivery policy to require manual toll-price review.
6. Excludes customer addresses and all order/payment/dispatch authority from normalized output.

## Deliberately not implemented

- API key or Google Cloud secret handling;
- HTTP transport;
- live route calls or billing;
- Google project/API enablement;
- runtime origin-address configuration;
- production quote publication;
- retries;
- WooCommerce order mutation;
- payment authorization;
- vehicle dispatch.

Any live Google Routes activation remains a separate readiness-gated production integration decision.

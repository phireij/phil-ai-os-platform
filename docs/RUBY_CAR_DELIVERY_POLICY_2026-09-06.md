# Ruby’s Cake Delights — Ruby Car Delivery Policy

Date: 2026-09-06
Status: CEO-approved foundation policy
Scope: Sprint 3 WooCommerce Foundation / pre-production only
Supersedes: the car-delivery distance/pricing items previously marked pending in `RUBY_FULFILLMENT_CUSTOMIZATION_MOBILE_DECISIONS_2026-09-06.md`

## Fixed origin

Every Ruby-operated car-delivery route starts from Ruby’s Cake Delights shop in Ichikawa. The application contract uses the stable origin reference `ruby_shop_ichikawa`; a future routing adapter must resolve that reference to the approved shop address and must not accept a customer-selected origin.

## Service area

Automatic eligibility is limited to destinations in:

- Chiba
- Tokyo
- Kanagawa
- Saitama

Being inside one of these prefectures does not guarantee service. Distance, driving time, product sensitivity, route conditions, toll/parking evidence, requested date/time, and Ruby operational capacity remain relevant.

## Customer-facing one-way distance pricing

Actual road/driving distance from the shop to the customer is the pricing distance. Straight-line distance must not be used.

- 0–10 km: minimum delivery fee **¥2,500**.
- Over 10 km through 30 km: ¥2,500 + **¥150 per started km** above 10 km.
- Over 30 km through 50 km: fee at 30 km (¥5,500) + **¥200 per started km** above 30 km.
- Over 50 km through 80 km: **manual quotation required**; no automatic final fee.
- Over 80 km: **normally unavailable** and fail-closed.

Reference examples:

- 8 km → ¥2,500
- 15 km → ¥3,250
- 20 km → ¥4,000
- 30 km → ¥5,500
- 40 km → ¥7,500
- 50 km → ¥9,500

The customer-facing fee uses one-way distance. Ruby may account for the return trip internally when reviewing whether pricing remains economically appropriate.

## Driving-time safeguard

Any route estimated above **75 minutes one-way** requires manual review even when distance is 50 km or less.

## Tolls and parking

- Expressway/toll charges are separate from the distance-based delivery fee.
- When an approved routing provider returns a known toll amount, it may be added to the provisional quote.
- If a route is expected to use toll roads but the toll amount is unavailable, the order requires manual review.
- Exceptional parking costs or unusual parking constraints require manual review and may be added to the final quote before payment.
- The system must not choose an unsafe route for a fragile cake solely to minimize toll cost.

## Sensitive cakes

Product rules may restrict structurally sensitive cakes (including some 2- or 3-layer cakes) to:

- shop pickup; and/or
- Ruby car delivery.

Yamato may be disabled product-by-product when transport risk is unacceptable. Product sensitivity and transport eligibility remain catalog attributes and do not derive solely from price or number of layers.

## Quote lifecycle and authority

Ruby car-delivery pricing is provisional until the order’s fulfillment review is complete.

1. Customer submits the destination plus requested delivery date/time.
2. Approved routing logic obtains one-way driving distance/time and, when available, toll evidence from the fixed shop origin.
3. Phil AI OS applies the approved distance/time/service-area rules.
4. Automatic-range routes receive a provisional delivery quote; exception routes fail closed to manual review or unavailable status.
5. Ruby reviews exceptions, sensitive-cake constraints, toll/parking issues, and operational availability as needed.
6. The delivery method and final delivery fee are confirmed before the KOMOJU payment link is issued.

This policy does **not** authorize payment, vehicle dispatch, production WooCommerce mutation, or automatic fulfillment.

## Future routing adapter

A future Google Routes API (or other separately approved routing provider) adapter may supply road distance, duration, and toll evidence. API credentials must remain inside the approved secret boundary. Routing integration must be read-only with respect to commerce state and must not finalize a quote or payment merely because the API returns a route.

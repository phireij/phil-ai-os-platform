# Ruby’s Cake Delights — Fulfillment, Customization, and Mobile-First Decisions

Date: 2026-09-06
Status: CEO-approved foundation decisions, with explicitly noted pending business confirmations
Scope: Sprint 3 WooCommerce Foundation / pre-production architecture

## Decision principle

Modify the foundation now, before finalizing the production catalog, but do not rush any of these changes into production. All production writes, live payment execution, live SMS, DNS/public cutover, and final Go/No-Go remain separately governed.

## 1. Shipping temperature classes and mixed carts

- Products must support at least these fulfillment temperature classes:
  - `ambient`
  - `chilled`
  - `frozen`
- Products may additionally declare compatibility such as `cool_eligible` when an ambient item can safely travel chilled.
- For mixed carts, use the most restrictive compatible shipping mode rather than blindly preserving the cheapest item-level method.
- Example: a chilled cake plus ambient items that are marked `cool_eligible` may default to Yamato Cool TA-Q-BIN chilled.
- Yamato Cool TA-Q-BIN safety ceiling remains Size 120 / 15 kg. If the packed order exceeds that ceiling, the system must fail closed into one of these outcomes:
  - split into multiple parcels;
  - choose another allowed fulfillment method;
  - route for manual review.
- Default cake-box size may be Size 80, but the final parcel size and shipping charge may be revised after packing/combination review before payment is requested.

## 2. Ambient shipping and optional chilled upgrade

- Ambient-only carts default to regular Yamato TA-Q-BIN.
- Offer an optional chilled upgrade only when every item in the shipment is compatible with chilled transport.
- Do not offer frozen shipping as a generic upgrade for ambient products.

## 3. Yamato delivery time-window selection

- Offer Yamato delivery-time selection to all Yamato customers.
- For cake shipments, time-window selection should be required.
- For ambient-only orders, allow `No preference / 指定なし`.
- The exact Yamato-supported time-window choices must remain configuration-driven rather than hard-coded into product content.

## 4. Requested versus confirmed delivery date

- Checkout must collect a **Requested Delivery Date**, not represent it as guaranteed.
- The order flow must distinguish:
  - requested date/time;
  - fulfillment feasibility review;
  - proposed alternative date(s), when necessary;
  - customer acceptance/confirmation;
  - confirmed delivery date/time;
  - final quote/payment request.
- If the requested date cannot be fulfilled, Ruby / Phil AI OS may propose an earlier and/or later viable date before sending the final payment link.

## 5. Product add-ons — hybrid model

- Use a hybrid model:
  - simple customer-facing options on the relevant cake product page;
  - real underlying SKUs for paid add-ons when inventory/pricing/accounting benefits from SKU-level tracking.
- Examples include candles, number candles, message plaques, and selected cake extras.
- **Reminder checkpoint:** after the owner submits/finalizes the production product catalog, explicitly remind the owner to define the final add-on SKU list, pricing, inventory behavior, and which add-ons appear inline on cake product pages.

## 6. Custom cakes and image uploads

- Custom cakes must use a separate product/workflow from basic fixed-design cakes.
- The custom-cake request may collect size/servings, flavor, layers, theme/colors, inscription, requested date, notes, budget, and reference images.
- Reference photos/images must be uploadable through the customer flow and handled as private order inputs rather than assumed-public media.
- Custom-cake pricing is quote-based and may be changed after Ruby reviews the request, before the customer receives the final payment link.
- Basic cakes remain normal products with fixed/base pricing and bounded options.

## 7. Photo / edible toppers

- Photo/edible toppers are **not standalone products for sale**.
- They may be offered only as cake-related customization/add-on options where applicable.

## 8. Cake icing option — pending Ruby confirmation

Business note to retain for later confirmation:

- Icing may be optional on cake products, especially because heavier icing can increase damage risk during Yamato delivery.
- If icing is selected, default color is expected to be white.
- Additional colors may carry an extra charge, with a working example of **¥200 per additional color**.
- The exact surcharge and whether Ruby still wants this policy are **pending confirmation from Ruby**.
- Do not activate or hard-code the surcharge until confirmed.

## 9. Ruby car delivery for sensitive cakes

- Add a separate fulfillment mode for Ruby-operated car delivery.
- Structurally sensitive cakes, including some 2- or 3-layer cakes, may be restricted to:
  - shop pickup;
  - Ruby car delivery;
  - with Yamato disabled where unsafe.
- Current practical service area is Chiba, Tokyo, Kanagawa, and Saitama; this is an operating boundary, not a blanket promise to cover every address in those prefectures.
- Delivery pricing should support:
  - a minimum fee of ¥2,500;
  - an included maximum distance to be decided;
  - incremental charges beyond that distance;
  - possible manual override for tolls, parking, exceptional routes, or operational constraints.
- Automated route-distance/time calculation may later use an approved mapping/routing API, but exact pricing bands and distance ceiling remain a business decision to be finalized before activation.

## 10. Payment merchant fees

- Do not add a separate payment-processing/merchant surcharge to the customer at checkout.
- Merchant-processing cost should be absorbed into normal pricing strategy rather than exposed as a payment-method surcharge.

## 11. Mobile-first UI/UX requirement

- The customer experience must be **mobile-first** because the majority of Ruby’s customers order using mobile devices.
- Mobile is the primary design and acceptance target for:
  - product discovery;
  - cake customization/add-ons;
  - image upload;
  - requested date/time selection;
  - shipping-method selection;
  - address entry;
  - quote review;
  - payment-link handoff.
- Desktop remains a supported first-class experience and must be tested carefully; mobile-first does not mean desktop-neglected.
- Responsive acceptance testing must include both mobile and desktop layouts before production release, with special attention to long forms, upload controls, option selectors, price/quote visibility, and checkout readability.

## 12. Foundation implementation direction

The target order lifecycle is:

1. Customer selects products/customizations and submits requested delivery information.
2. Phil AI OS evaluates shipping temperature, compatibility, parcel constraints, fulfillment method, and whether manual review is required.
3. Ruby reviews exceptions/custom cakes/sensitive delivery cases as needed.
4. Final delivery method/date, parcel size/shipping fee, add-ons, and any custom quote are confirmed.
5. Customer receives the final payment request/link only after the quote is ready.
6. Payment and fulfillment proceed under existing production-readiness and governance controls.

## Explicitly pending business decisions

- Final icing policy and additional-color surcharge.
- Final add-on SKU catalog and prices — remind owner after production product catalog submission.
- Exact Ruby car-delivery included distance, incremental pricing formula/bands, and exception handling.
- Product-by-product temperature compatibility (`ambient`, `chilled`, `frozen`, `cool_eligible`).
- Product-by-product eligibility for Yamato versus pickup versus Ruby car delivery.

No pending item above authorizes production activation by itself.

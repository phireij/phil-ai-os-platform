# Ruby WooCommerce Japan Tax Readiness — 2026-09-02

**Environment:** Hostinger WordPress/WooCommerce pre-production  
**Authority:** A0 / preparation only / no live activation  
**Status:** IMPLEMENTATION CANDIDATE PREPARED / BUSINESS TAX STATUS CONFIRMATION REQUIRED

## Verified current state

The 2026-09-02 bounded read-only audit confirmed:

- currency: JPY;
- WooCommerce tax calculation: disabled;
- prices-entered-with-tax flag: false;
- no approved production catalog is loaded;
- KOMOJU remains test-key only.

No tax, catalog, payment, DNS, or production setting was changed by this review.

## Primary-source interpretation

The National Tax Agency states that Japan's standard consumption-tax rate is
10% and the reduced rate is 8% for qualifying food and drink other than alcohol
and dining out. Its current reduced-rate Q&A also states:

- food sold through mail order can qualify for the reduced rate;
- separately charged shipping for a food sale is not itself eligible for the
  reduced rate;
- when shipping is included in a single food-product price and no separate
  shipping charge is requested, the food transaction can remain subject to the
  reduced rate;
- consumer-facing advertised prices must show the tax-inclusive total.

Primary references:

- [NTA consumption-tax basic knowledge](https://www.nta.go.jp/english/taxes/consumption_tax/01.htm)
- [NTA reduced-rate Q&A, current individual examples](https://www.nta.go.jp/taxes/shiraberu/zeimokubetsu/shohi/keigenzeiritsu/pdf/qa/03-01.pdf)
- [NTA total-price display rule](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shohi/6902.htm)
- [WooCommerce core tax settings](https://woocommerce.com/document/setting-up-taxes-in-woocommerce/)

## Candidate WooCommerce model

Subject to accountant/CEO confirmation of Ruby's consumption-tax and invoice
status, the pre-production candidate should use:

1. tax calculations enabled;
2. product prices entered inclusive of tax;
3. catalog, cart, and checkout prices displayed inclusive of tax;
4. a reduced-rate product tax class for qualifying cakes/food;
5. a standard-rate tax class for separately charged Yamato shipping and other
   separately charged services or fees;
6. explicit per-product tax classification rather than a global assumption;
7. checkout/order evidence that separates totals by applicable rate;
8. refund QA that preserves the original tax-rate split.

## Required decision inputs before configuration

- Is Ruby currently a consumption-tax taxable business?
- Is Ruby registered as a qualified invoice issuer, and what registration
  number/receipt treatment must be shown?
- Are all WooCommerce catalog items qualifying food, or will any non-food,
  alcoholic, dine-in, service, topper, utensil, packaging, or mixed-bundle item
  require a different class?
- Will Yamato shipping always be shown as a separate charge?
- How should COD and other separately charged fees be classified and displayed?

## Pre-production acceptance tests after approval

- pickup-only qualifying food;
- Yamato delivery with a separate shipping charge;
- each shipping zone and size class;
- frozen-only and chilled-only products;
- any mixed-rate cart introduced later;
- discounts, cancellation, full refund, and partial refund;
- bilingual catalog/cart/checkout/order-email tax wording;
- total-price display and rate-separated order evidence.

## Gate

Do not enable or populate WooCommerce tax tables until the required business
status inputs are confirmed. The eventual change must remain pre-production,
reversible, backed up, and followed by checkout-total evidence before any
cutover proposal.

`production_publish_authorized: false`  
`komoju_live_authorized: false`  
`tax_configuration_authorized: false`

`PHIL_AI_OS_RUBY_WOOCOMMERCE_JAPAN_TAX_READINESS_PREPARED`

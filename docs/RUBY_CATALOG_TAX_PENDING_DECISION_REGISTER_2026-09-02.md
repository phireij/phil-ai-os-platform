# Ruby Catalog and Tax Pending Decision Register — 2026-09-02

**Environment:** Hostinger WordPress/WooCommerce pre-production  
**Authority:** A0 / preparation only / no WooCommerce mutation  
**Status:** INPUT PACKAGE PREPARED / CEO AND TAX-STATUS RESPONSES PENDING

## Purpose

This is the single reference for the information still required before the
approved Ruby catalog and tax-inclusive checkout candidate can be configured.
It does not authorize catalog loading, tax-table changes, publishing, KOMOJU
Live Mode, SMS sending, DNS changes, or any production action.

## Product catalog — pending

For each product that Ruby approves for launch, record:

1. SKU;
2. English and Japanese name, description, and slug;
3. tax-inclusive customer price in JPY;
4. approved category;
5. approved primary image and bilingual alt text;
6. Yamato Cool size class: `cool-60`, `cool-80`, `cool-100`, or `cool-120`;
7. temperature eligibility: frozen, chilled, or both;
8. pickup eligibility and delivery eligibility;
9. candidate tax class: reduced-rate food, standard rate, or exempt;
10. explicit CEO approval evidence.

Until these are complete, every product stays absent from WooCommerce. The
intake contract additionally requires any prepared record to remain `draft`
and `hidden`.

## Business tax status — pending

The following decisions must be confirmed before tax configuration:

1. Is Ruby currently a consumption-tax taxable business or an exempt business?
2. Is Ruby registered as a qualified invoice issuer?
3. If registered, what qualified-invoice registration number and receipt
   treatment must be used?
4. Will Yamato shipping always appear as a separate customer charge?
5. Has the tax treatment of COD and any other separately charged fee been
   confirmed?
6. Based on confirmed professional/business guidance, should the pre-production
   candidate use WooCommerce tax tables or retain tax calculation disabled?

No answer is inferred. Tax status and implementation route remain `pending`
until evidence is supplied.

## Prepared technical intake

- Machine-readable template:
  `commerce/woocommerce/fixtures/production-catalog-intake.template.json`
- Contract:
  `contracts/commerce/catalog-tax-intake.schema.json`
- Readiness evaluator:
  `phil_ai_os_woocommerce.catalog_readiness.evaluate_catalog_tax_readiness`

The evaluator reports catalog readiness and tax-decision readiness separately.
Even when both become GREEN, it always returns:

`mutation_authorized: false`  
`production_publish_authorized: false`

An explicit, later CEO-approved pre-production change gate is still required.

## Current gate

- Catalog finalization: **PENDING**.
- Catalog approval evidence: **PENDING**.
- Consumption-tax status: **PENDING**.
- Qualified-invoice status: **PENDING**.
- WooCommerce tax implementation route: **PENDING**.
- Pre-production catalog/tax mutation: **NOT AUTHORIZED**.
- Production publish/cutover: **NOT AUTHORIZED**.

`PHIL_AI_OS_RUBY_CATALOG_TAX_PENDING_INPUTS_RECORDED`

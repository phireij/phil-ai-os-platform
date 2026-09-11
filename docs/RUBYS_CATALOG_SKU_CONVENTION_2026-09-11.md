# Ruby's Cake Delights — Catalog SKU Convention

**Date:** 11 September 2026  
**Status:** PRE-PRODUCTION / CATALOG AUTHORING STANDARD  
**Roadmap:** Sprint 3 primary; final owner-approved Initial Launch Catalog V1 remains the closure gate

## Standard

Use the pattern:

`RCD-PRODUCT-FORM[-OPTION]`

Where:

- `RCD` = Ruby's Cake Delights.
- `PRODUCT` = short stable product/flavor code.
- `FORM` = physical form/shape code.
- `OPTION` = optional physical purchasable distinction, normally size or another stock-bearing option.

The SKU represents the physical sellable identity. Customer customization instructions, uploaded reference images, colors, messages and similar order-specific choices must not be encoded into the SKU unless Ruby intentionally sells that choice as a distinct stock-bearing variation.

## Approved starting codes

| Meaning | Code |
| --- | --- |
| Moist Chocolate | `MCH` |
| Round | `RD` |
| Square | `SQ` |

Examples:

- `RCD-MCH-RD-15` = Ruby's Cake Delights / Moist Chocolate / Round / 15 cm.
- `RCD-MCH-RD-21` = Ruby's Cake Delights / Moist Chocolate / Round / 21 cm.
- `RCD-MCH-SQ-21` = Ruby's Cake Delights / Moist Chocolate / Square / 21 cm.

## Rules

1. Use uppercase ASCII letters and numbers only inside segments.
2. Separate segments with a single hyphen.
3. Do not reuse a SKU for a different physical product or variation.
4. Flavor/product-family codes should remain stable once used in production.
5. Shape/form should be explicit when it changes the physical product page or fulfillment identity.
6. Size belongs in the optional final segment when it is a purchasable variation.
7. Do not append `STD`, `CUS`, customer names, dates or design instructions merely to represent customization metadata.
8. If a future product genuinely needs another stock-bearing distinction beyond this four-segment pattern, extend the convention deliberately rather than inventing ad-hoc SKUs in the catalog.

## Catalog integration

The canonical catalog still requires every simple product and every purchasable variation to have a unique SKU. The helper in `commerce/woocommerce/src/phil_ai_os_woocommerce/sku_policy.py` provides deterministic build/parse validation for this convention but does not authorize catalog publication or any WooCommerce production mutation.

## Governance

This convention is an authoring and validation standard only. It does not create products, variations, inventory, shipping methods, payments, publications or production authority.

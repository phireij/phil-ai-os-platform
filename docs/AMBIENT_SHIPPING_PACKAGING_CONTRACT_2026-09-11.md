# Ambient Shipping Packaging Contract

**Date:** 11 September 2026  
**Status:** PRE-PRODUCTION / CODE CONTRACT GREEN CANDIDATE  
**Roadmap:** Sprint 3 primary; owner-approved production catalog remains the Sprint 3 closure gate

## Business decision

Ruby's Cake Delights will support smaller ambient-shipping packages for products such as brownies and caramel bars rather than forcing every 常温 order into regular Yamato Size 60 packaging.

The initial package classes are:

| Package class | Carrier service intent | Use |
| --- | --- | --- |
| `ambient_compact` | Yamato TA-Q-BIN Compact | Small, physically verified ambient products such as brownie/caramel-bar boxes |
| `ambient_60` | Regular Yamato TA-Q-BIN | Default/fallback ambient carton |
| `ambient_80` | Regular Yamato TA-Q-BIN | Larger ambient orders |
| `ambient_100` | Regular Yamato TA-Q-BIN | Larger ambient orders |
| `ambient_120` | Regular Yamato TA-Q-BIN | Larger ambient orders |

## Fail-closed selection rule

A product must explicitly declare its minimum safe ambient package class in the final catalog. The system never downgrades below that minimum.

For `ambient_compact` products:

- A single quantity-1 SKU that has been physically verified for Compact may select TA-Q-BIN Compact.
- Multiple units or mixed Compact-only lines do **not** automatically assume they fit. They conservatively fall back to regular Size 60 unless packing evidence confirms Compact fit.
- If packing evidence contradicts the product minimum and proposes a smaller class, the decision fails closed for manual review.
- Packing evidence may safely upgrade to a larger class.

This rule intentionally avoids guessing from product type alone. Actual fit, cushioning and box closure must be verified operationally before a SKU is marked `ambient_compact` in the production catalog.

## Brownies and caramel bars

Brownies and caramel bars are the first intended candidates for `ambient_compact`, subject to physical package-fit confirmation and final catalog data. No SKU is hard-coded into the policy; eligibility is driven by catalog facts so package changes do not require source-code changes.

## WooCommerce implementation path

The code contract added in `commerce/woocommerce/src/phil_ai_os_woocommerce/ambient_packaging.py` provides deterministic package selection before any live WordPress/WooCommerce mutation.

After the final catalog supplies each product/variation's package class, the next governed integration step is to map the decision to WooCommerce shipping configuration:

- `ambient_compact` -> customer-visible Yamato Compact option/rate;
- `ambient_60+` -> regular Yamato ambient option/rate by package class;
- incompatible or unresolved packing -> fail closed/manual review rather than undercharge or oversell shipping capacity.

Exact customer-facing rates remain a separate pricing/configuration concern and are not introduced by this contract.

## Production boundary

This change does **not** modify the live Hostinger WordPress site, WooCommerce shipping zones, carrier rates, checkout, payments, inventory, DNS, SMS, or publication state.

`production_mutation_authorized` remains `false` in the package decision. Live WooCommerce shipping-method creation/configuration remains behind the existing production approval gate.

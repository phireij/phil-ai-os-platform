# Ruby's Working Catalog Subset — 11 September 2026

**Status:** WORKING OWNER SOURCE / INCOMPLETE INITIAL-LAUNCH SUBSET  
**Source:** `Product Catalog ver2.docx` in the owner's Google Drive  
**Source file ID:** `13gbwu9_l59AalbKofUJZVX4IziYCKZS7`  
**Observed modified time:** `2026-09-11T02:24:32.696Z`

This record captures only facts currently present in the owner-maintained catalog. It is deliberately **not** an Initial Launch Catalog V1 approval, does not claim the launch subset is complete, and grants no WooCommerce production-write or publication authority.

## Current products

### Moist Chocolate Round Cake

- WooCommerce intent: variable product.
- Flavor/family: Moist Chocolate.
- Form: Round Cake.
- English description supplied by owner.
- Temperature marked: Frozen.
- Available for: Both pickup and delivery.
- Minimum preparation time: 5 days.
- Maximum advance-order period: 2 months.
- Allergens supplied: Dairy (Milk, Butter, or Cream), Wheat (Gluten), Eggs.
- 15 cm variation: `RCD-MCH-RD-15`, ¥3,500, approved in source.
- 21 cm variation: owner confirmed the intended SKU is `RCD-MCH-RD-21`, ¥5,500. The source currently contains the typo `RCS-MCH-RD-21`; ingestion must normalize only this explicitly confirmed typo and must not silently correct other owner data.
- Parent/product-family reference shown: `RCD-MCH-RD`.

### Fudgy Milky Bar

- WooCommerce intent: simple product.
- SKU: `RCD-BAR-FMB`.
- Price: ¥250.
- Flavor/family: Caramel.
- Form: Rectangle.
- Category selected: Other.
- Temperature marked: Chilled and 常温 (ambient).
- Package size: depends on total pieces.
- Available for: Both pickup and delivery.
- Production policy: Made to order.
- Minimum preparation time: 3 days.
- Maximum advance-order period: 2 months.
- Product photo set marked attached.
- Allergens supplied: Wheat, Dairy (Milk/Butter), Eggs, Nuts.
- Ambient Compact remains only a candidate until physical fit/cushioning is confirmed; quantity-dependent packing must be able to fall back to a larger ambient class.

### Cheezy Ensaymada

- WooCommerce intent: simple product.
- SKU shown: `RCD-BRD-ENS-1`.
- Flavor/family: Bread.
- Category selected: Bread.
- Temperature marked: Chilled; 常温 is present but not checked in the current source.
- Package size: depends on total items.
- Available for: Both pickup and delivery.
- Production policy: Made to order.
- Minimum preparation time: 3 days.
- Maximum advance-order period: 2 months.
- Product photo set marked attached.
- Allergens supplied: Wheat, Dairy (Milk/Butter), Eggs.

## Missing or unresolved fields

The current working source does not yet support a production-ready catalog handoff. At minimum, the following remain unresolved in the source and must fail closed rather than be invented:

- Japanese product names and Japanese short descriptions;
- final approved category hierarchy/slugs for WooCommerce;
- verified media references/keys suitable for ingestion;
- complete source provenance per product;
- final shipping/package class where the source says packaging depends on quantity/items;
- final temperature interpretation where multiple modes are checked or ambient is not checked;
- complete production/stock policy for Moist Chocolate Round Cake where the extracted source does not expose a selected value;
- final owner confirmation that the intended initial-launch subset is complete;
- explicit Initial Launch Catalog V1 approval reference.

The current product schema requires bilingual English/Japanese localized text and, for delivery-enabled products, a concrete shipping class and at least one temperature mode. Therefore no production-ready catalog payload should be fabricated from this partial source.

## Safe implementation rules

1. Treat these three entries as a working subset for validation, mapping, dry-run planning, SKU collision checks, and pre-production preparation only.
2. Preserve `catalog_approved=false` and `scope_complete_for_intended_initial_launch=false` until the owner explicitly closes those gates.
3. Keep products draft/hidden in controlled intake/pre-production planning.
4. Never infer missing Japanese copy, media provenance, packaging fit, or temperature policy as owner-approved facts.
5. Apply only the explicitly confirmed SKU correction `RCS-MCH-RD-21` → `RCD-MCH-RD-21`.
6. Twilio remains a separate external blocker and does not block catalog preparation; no SMS send authority is granted.
7. No live WooCommerce product, shipping, payment, inventory, DNS, or publication mutation is authorized by this record.

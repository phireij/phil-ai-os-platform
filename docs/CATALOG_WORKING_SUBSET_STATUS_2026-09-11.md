# Catalog Working Subset Status — 11 September 2026

**Sprint:** Sprint 3 — WooCommerce Foundation  
**Status:** owner-maintained working subset captured; Initial Launch Catalog V1 remains incomplete and unapproved  
**Current source:** `Product Catalog ver2.docx` in the owner's Google Drive

## Captured working subset

The current owner source contains three working products:

1. Moist Chocolate Round Cake
   - variable product intent
   - `RCD-MCH-RD-15` — ¥3,500
   - `RCD-MCH-RD-21` — ¥5,500
   - the source typo `RCS-MCH-RD-21` has an explicit owner-confirmed correction to `RCD-MCH-RD-21`
2. Fudgy Milky Bar
   - simple product
   - `RCD-BAR-FMB` — ¥250
3. Cheezy Ensaymada
   - simple product
   - `RCD-BRD-ENS-1` — ¥300
   - the ¥300 price is supported by supplemental owner screenshot evidence after the Word text extractor omitted that lower table row

## Merged safeguards

- PR #240 captured the current three-product source as a machine-readable, non-authorizing working fixture.
- PR #241 added fail-closed validation that keeps the working subset incomplete/unapproved, validates Ruby SKU policy, preserves unique SKUs, and requires explicit evidence for the 21 cm Moist Chocolate SKU correction.
- PR #242 added a structured catalog-gap report and corrected Cheezy Ensaymada to ¥300 before merge.

These safeguards allow owner-independent preparation without converting the working subset into a production-ready catalog.

## Current unresolved catalog gaps

The following remain real owner/source gaps and should not be invented:

- final owner confirmation that the intended initial-launch subset is complete;
- explicit Initial Launch Catalog V1 approval reference;
- Japanese product names and Japanese descriptions;
- final approved category hierarchy/slugs for the launch subset;
- verified media ingestion references/provenance;
- final shipping/package classification where packing depends on total pieces/items;
- physical fit/cushioning evidence for any `ambient-compact` candidate;
- final customer-facing Yamato shipping/rate policy.

## Governance

The working subset is valid for validation, mapping, dry-run planning and pre-production preparation only. It does not authorize:

- WooCommerce production product/category/media mutation or publication;
- live shipping-rate changes;
- KOMOJU live payment execution;
- unrestricted Twilio sending;
- DNS/domain switching;
- production inventory synchronization;
- higher autonomy.

Sprint 3 remains the current primary sprint. Sprint 4 remains bounded parallel acceleration only.

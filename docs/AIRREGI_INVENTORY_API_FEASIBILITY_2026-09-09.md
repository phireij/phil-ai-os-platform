# AirREGI Inventory API Feasibility — WooCommerce Quick Pickup

**Date:** 9 September 2026  
**Status:** Investigation started / read-only / no production mutation  
**Roadmap position:** Sprint 3 primary; bounded parallel feasibility work while waiting for the owner-approved production catalog

## Objective

Determine whether Ruby's Cake Delights can implement a WooCommerce-based Quick Pickup flow for ready-stock shop products while keeping AirREGI as the physical-stock source of truth, avoiding the separate AirREGI モバイルオーダー 店外版 service where practical.

## Business target

Candidate flow:

1. AirREGI remains authoritative for physical shop inventory.
2. Phil AI OS exposes only eligible ready-stock items to WooCommerce Quick Pickup.
3. WooCommerce handles customer-facing ordering, pickup time selection, bilingual UX, KOMOJU payment and notifications.
4. Online reservations are subtracted from available-to-sell stock immediately to reduce oversell risk.
5. Confirmed WooCommerce sales must reconcile back to the AirREGI stock/sales workflow before any production launch.

Made-to-order/custom cakes remain outside this ready-stock inventory domain unless explicitly classified otherwise.

## Public-source findings — initial pass

### 1. AirREGI has native inventory management

AirREGI's inventory management supports stock quantities, stock-managed products, variations, stock adjustments and stock movement tied to register transactions. Product variations can be managed separately.

This confirms AirREGI is technically suitable as the operational physical-stock authority for ready-stock products.

### 2. AirREGI exposes a Data Integration API

AirREGI Back Office provides a `データ連携API` setting where an operator can enable API use and obtain an API key and API token.

The public AirREGI FAQ currently describes the data that can be linked through this API as:

- transaction information, including checkout, receipt printing, slip deletion, checkout correction, returns/refunds and refund cancellation;
- cash-in/cash-out information; and
- settlement information.

### 3. Critical feasibility finding: inventory is not listed in the public Data Integration API scope

The same current public FAQ does **not** list product master data or inventory quantities among the data exposed through the documented Data Integration API.

Therefore, at this stage we must **not** assume that AirREGI provides a supported public inventory read/write endpoint for arbitrary custom integrations.

This changes the architecture status from "API inventory bridge likely available" to:

> **AirREGI inventory API integration is UNPROVEN and must remain fail-closed until endpoint-level capability is confirmed.**

### 4. AirREGI inventory itself remains usable even if direct API inventory access is unavailable

AirREGI Back Office and the AirREGI app expose inventory-management screens and support stock management per product/variation. This leaves several fallback integration patterns to assess, such as controlled manual synchronization, CSV-based workflows if supported, or an alternative authoritative inventory architecture.

No fallback should be selected until its operational and oversell risks are evaluated.

## Feasibility questions still open

1. Is there an official product/inventory endpoint not exposed in the public FAQ?
2. Is that endpoint available to ordinary AirREGI merchants or only approved partner/head-office systems?
3. Can stock quantities be read, written, or both?
4. What identifiers are stable enough to map AirREGI items/variations to WooCommerce SKUs?
5. What are rate limits, freshness guarantees and error semantics?
6. Is webhook/event delivery available for stock-affecting POS sales, or would polling be required?
7. Can WooCommerce sales be registered back into AirREGI in a supported way so physical stock and POS sales remain reconciled?
8. If stock writes are unsupported, can transaction ingestion through the documented API safely produce the needed AirREGI inventory movement, or is the API outbound/read-only from AirREGI's perspective?
9. What is the safest oversell-control model during synchronization delay?

## Candidate architecture — only if supported endpoints are verified

```text
AirREGI physical stock
        |
        v
Phil AI OS AirREGI Inventory Adapter
        |
        +--> canonical item/SKU mapping
        +--> available-to-sell = AirREGI stock - active Woo reservations
        |
        v
WooCommerce Quick Pickup
        |
        +--> pickup slot
        +--> KOMOJU payment
        +--> customer/staff notifications
        |
        v
Governed reconciliation back to AirREGI
```

Production requirements before activation:

- proven supported stock interface;
- deterministic AirREGI ↔ Woo SKU mapping;
- reservation/idempotency contract;
- oversell fail-close behavior;
- reconciliation and audit trail;
- rollback/manual recovery procedure;
- security boundary for AirREGI API credentials;
- explicit production authorization.

## Current conclusion

**Quick Pickup in WooCommerce remains feasible as a product feature.** The unresolved point is not WooCommerce or KOMOJU; it is the supported mechanism for keeping AirREGI physical inventory authoritative in near-real time.

The current public AirREGI Data Integration API documentation is insufficient to approve a direct inventory bridge because its documented linked-data scope does not include inventory/product quantities.

Accordingly:

- Do not apply for or depend on モバイルオーダー 店外版 yet solely for technical reasons.
- Do not implement production AirREGI inventory writes or scrape AirREGI UI.
- Continue endpoint/capability investigation in parallel with Sprint 3 catalog completion.
- Preserve AirREGI as the intended physical-stock authority unless the feasibility investigation shows that a different architecture is safer.

## Governance

This investigation is read-only and non-authorizing. It does not enable production AirREGI access, WooCommerce stock mutation, real payment execution, live SMS, publication, DNS changes, or higher autonomy.

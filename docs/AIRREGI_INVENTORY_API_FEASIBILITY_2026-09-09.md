# AirREGI Inventory API Feasibility — WooCommerce Quick Pickup

**Date:** 9 September 2026  
**Last reviewed:** 11 September 2026  
**Status:** Investigation active / read-only / no production mutation  
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

## Public-source findings

### 1. AirREGI has native inventory management

AirREGI inventory management supports stock quantities, stock-managed products, variations, stock adjustments and stock movement tied to register transactions. Product variations can be managed separately.

### 2. AirREGI exposes a Data Integration API

AirREGI Back Office provides a `データ連携API` setting where an operator can enable API use and obtain an API key and API token.

The current public AirREGI FAQ describes the linked-data scope as:

- transaction information, including checkout, receipt printing, slip deletion, checkout correction, returns/refunds and refund cancellation;
- cash-in/cash-out information; and
- settlement information.

Official source: `APIで各種システムとデータ連携して利用する方法`  
https://faq.airregi.jp/hc/ja/articles/48202752451353-API%E3%81%A7%E5%90%84%E7%A8%AE%E3%82%B7%E3%82%B9%E3%83%86%E3%83%A0%E3%81%A8%E3%83%87%E3%83%BC%E3%82%BF%E9%80%A3%E6%90%BA%E3%81%97%E3%81%A6%E5%88%A9%E7%94%A8%E3%81%99%E3%82%8B%E6%96%B9%E6%B3%95

### 3. Inventory is still not documented in the public API scope

The same current public FAQ does **not** list product master data or inventory quantities among the exposed Data Integration API data.

Therefore:

> **AirREGI direct inventory API integration remains UNPROVEN and must stay fail-closed until endpoint-level capability is confirmed.**

The public list of API-connected systems presents a defined set of supported external systems rather than a documented general-purpose inventory API contract for arbitrary merchant-built clients.

Official source: `APIでデータ連携できる各種システム一覧` — updated 3 July 2026.  
https://faq.airregi.jp/hc/ja/articles/48210229202329-API%E3%81%A7%E3%83%87%E3%83%BC%E3%82%BF%E9%80%A3%E6%90%BA%E3%81%A7%E3%81%8D%E3%82%8B%E5%90%84%E7%A8%AE%E3%82%B7%E3%82%B9%E3%83%86%E3%83%A0%E4%B8%80%E8%A6%A7

### 4. CSV inventory fallback is officially supported

AirREGI officially supports inventory CSV workflows from Back Office:

- current stock quantities can be exported in an `在庫一括編集CSVファイル`;
- the CSV can be edited and uploaded to bulk-register/update inventory quantities;
- stocktake detail and summary CSV exports exist;
- product master data can be bulk-exported/edited through product-registration CSV workflows.

This means a **controlled CSV synchronization fallback is technically feasible** even if a supported direct inventory API is unavailable.

Official sources:

- `Airレジで出力できる様々なCSVデータ`  
  https://faq.airregi.jp/hc/ja/articles/360040566033-Air%E3%83%AC%E3%82%B8%E3%81%A7%E5%87%BA%E5%8A%9B%E3%81%A7%E3%81%8D%E3%82%8B%E6%A7%98%E3%80%85%E3%81%AACSV%E3%83%87%E3%83%BC%E3%82%BF
- `CSVファイルを利用した在庫数の一括登録・編集方法`  
  https://faq.airregi.jp/hc/ja/articles/360031015634-CSV%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB%E3%82%92%E5%88%A9%E7%94%A8%E3%81%97%E3%81%9F%E5%9C%A8%E5%BA%AB%E6%95%B0%E3%81%AE%E4%B8%80%E6%8B%AC%E7%99%BB%E9%8C%B2-%E7%B7%A8%E9%9B%86%E6%96%B9%E6%B3%95

### 5. Cross-system product-code mapping is supported

AirREGI documentation explicitly states that its `商品コード` field may use a product code defined by another inventory, sales, accounting or analytics service so the same code can be used across systems.

That makes an AirREGI product/variation ↔ WooCommerce SKU mapping operationally realistic without inventing a second identifier scheme.

Official source: `商品バリエーションの登録方法`  
https://faq.airregi.jp/hc/ja/articles/203358710-%E5%95%86%E5%93%81%E3%83%90%E3%83%AA%E3%82%A8%E3%83%BC%E3%82%B7%E3%83%A7%E3%83%B3%E3%81%AE%E7%99%BB%E9%8C%B2%E6%96%B9%E6%B3%95

## Feasibility questions still open

1. Is there an official product/inventory endpoint not exposed in the public FAQ?
2. Is that endpoint available to ordinary AirREGI merchants or only approved partner/head-office systems?
3. Can stock quantities be read, written, or both?
4. What are rate limits, freshness guarantees and error semantics if inventory endpoints exist?
5. Is webhook/event delivery available for stock-affecting POS sales, or would polling be required?
6. Can WooCommerce sales be registered back into AirREGI in a supported way so physical stock and POS sales remain reconciled?
7. If stock writes are unsupported, can a supported transaction interface safely produce the needed AirREGI inventory movement?
8. What is the safest oversell-control model during synchronization delay?
9. Can the inventory CSV download/upload process be automated through an officially supported endpoint, or must it remain an operator-assisted Back Office workflow?

## Candidate architecture A — preferred if supported inventory endpoints are verified

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

## Candidate architecture B — controlled CSV fallback

If direct inventory endpoints remain unavailable:

```text
AirREGI Back Office inventory CSV
        |
        v
Phil AI OS guarded CSV importer
        |
        +--> validate schema / timestamp / SKU mapping
        +--> calculate safe available-to-sell buffer
        +--> subtract active Woo reservations
        |
        v
WooCommerce Quick Pickup availability
        |
        v
operator-assisted or separately supported reconciliation to AirREGI
```

The CSV fallback is **not near-real-time**. It must therefore use conservative safety stock, snapshot freshness limits, automatic Quick Pickup suspension when the latest inventory snapshot is stale, and explicit reconciliation after Woo sales.

It is a viable fallback, not yet an approved production design.

## Production requirements before activation

- proven supported stock interface or formally accepted CSV fallback;
- deterministic AirREGI ↔ Woo SKU/product-code mapping;
- reservation/idempotency contract;
- stock snapshot freshness rule;
- oversell fail-close behavior;
- reconciliation and audit trail;
- rollback/manual recovery procedure;
- security boundary for AirREGI credentials/files;
- explicit production authorization.

## Current conclusion

**WooCommerce Quick Pickup remains feasible.** The unresolved point is the mechanism for keeping AirREGI physical inventory authoritative with acceptable freshness and reconciliation risk.

Two evidence-based paths now remain:

1. **Preferred:** direct inventory bridge, only if AirREGI confirms supported inventory/product endpoints for our merchant use case.
2. **Fallback:** guarded CSV inventory synchronization using AirREGI's officially supported stock CSV workflow, with conservative availability buffers and stale-data fail-close behavior.

Accordingly:

- Do not apply for or depend on モバイルオーダー 店外版 yet solely for technical reasons.
- Do not implement production AirREGI inventory writes or scrape AirREGI UI.
- Continue endpoint/capability investigation in parallel with Sprint 3 catalog completion.
- Preserve AirREGI as the intended physical-stock authority unless later evidence supports a safer architecture.
- Treat AirREGI `商品コード` and WooCommerce SKU alignment as the preferred cross-system identity strategy for ready-stock items.

## Governance

This investigation is read-only and non-authorizing. It does not enable production AirREGI access, WooCommerce stock mutation, real payment execution, live SMS, publication, DNS changes, or higher autonomy.

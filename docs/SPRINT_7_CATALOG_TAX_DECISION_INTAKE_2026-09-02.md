# Sprint 7 — Catalog & Tax Decision Intake

**Date:** 2026-09-02  
**Program:** Phil AI OS Platform  
**Purpose:** Resolve the two remaining commerce inputs needed before a later, separately approved WooCommerce pre-production configuration change.

## Governance boundary

This document is an intake checklist only.

It does **not** authorize:

- WooCommerce credentials or live connectivity;
- product/category/media writes;
- tax-table writes;
- production publishing;
- KOMOJU Live Mode or real payments;
- public-domain/DNS cutover;
- SMS sending;
- specialist enablement, a new execution task class, autonomy above A0, or Mission Control mutation authority.

Hermes remains bounded to the existing `general` task class and Mission Control remains read-only.

---

## Decision A — Approved production catalog

Provide only products that are approved for the initial production launch. Do not copy the old Website Builder test catalog by assumption.

For each approved product, confirm:

| Field | Required input |
|---|---|
| Product name — English | Final customer-facing English name |
| Product name — Japanese | Final customer-facing Japanese name |
| SKU | Unique production SKU |
| Regular price | Final JPY tax-inclusive customer price |
| Category | Approved category assignment |
| Shipping size class | Canonical Yamato size class, where delivery is allowed |
| Temperature eligibility | Frozen and/or chilled |
| Store pickup | Yes / No |
| Yamato delivery | Yes / No |
| Primary image | Approved source asset/reference |
| Additional images | Optional approved source assets/references |
| Description — English | Final customer-facing English description |
| Description — Japanese | Final customer-facing Japanese description |
| Launch approval | Approved / Pending |

### Catalog acceptance conditions

The catalog package can become **catalog-ready** only when:

1. the package itself is explicitly approved;
2. every product is explicitly approved;
3. every SKU is unique;
4. every product has at least one approved category;
5. every product has a primary approved media item;
6. no launch media still points to a fixture/test source;
7. price is confirmed tax-inclusive;
8. a tax-class candidate is assigned after Decision B is resolved;
9. intake products remain `draft` and `hidden` until a later configuration approval.

---

## Decision B — Ruby's Japan consumption-tax / qualified-invoice status

These are business/legal facts and must be confirmed from Ruby's actual current status or evidence. They must not be inferred by the platform.

Please confirm:

| Decision | Allowed intake values |
|---|---|
| Ruby's consumption-tax status | `taxable` / `exempt` |
| Qualified Invoice System status | `registered` / `not_registered` |
| Qualified invoice registration number | Required if registered |
| Yamato shipping charged separately to customer | `yes` / `no` |
| COD fee treatment | `not_offered` / `standard_rate` / `reduced_rate` / `other_confirmed` |
| Evidence/reference | Source or record supporting the decision |

### Current implementation candidates

The repository's current fail-closed intake contract allows these later implementation candidates only after the business facts are confirmed:

- `tax_tables_candidate` when Ruby is confirmed taxable;
- `tax_disabled_candidate` when Ruby is confirmed exempt.

The existing Japan tax readiness review records **8% qualifying-food / 10% separately charged shipping** only as a candidate configuration. It is not an authorization to enable tax tables.

---

## CEO decision response template

Use this compact format if convenient:

```text
CATALOG
Approved launch catalog: YES / NO
Catalog source/reference: <file, sheet, document, or explicit list>

TAX / INVOICE
Consumption-tax status: taxable / exempt
Qualified Invoice status: registered / not_registered
Registration number: <number or N/A>
Yamato shipping separately charged: yes / no
COD fee treatment: not_offered / standard_rate / reduced_rate / other_confirmed
Evidence/reference: <source>
```

If the approved catalog is supplied as a document or spreadsheet, the CTO office can transform it into the repository's machine-readable intake format without altering the underlying business decisions.

---

## What happens after both decisions are complete

1. Populate the machine-readable catalog/tax intake package.
2. Run the fail-closed readiness evaluator and Commerce CI.
3. Review resulting catalog-ready and tax-ready evidence.
4. Prepare a separate pre-production configuration proposal.
5. Obtain explicit CEO approval **before any WooCommerce write**.
6. Configure only the approved bounded scope and preserve rollback/audit evidence.

A GREEN intake evaluation means only **ready to propose pre-production configuration**. It never grants mutation or production-publish authority.

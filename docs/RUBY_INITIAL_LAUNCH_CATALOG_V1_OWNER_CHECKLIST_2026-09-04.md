# Ruby's Cake Delights — Initial Launch Catalog V1 Owner Checklist

**Date:** 4 September 2026  
**Purpose:** Sprint 3 owner handoff for the first real WooCommerce launch subset.

## Scope rule

The Initial Launch Catalog V1 **does not need to contain every Ruby's Cake Delights product**.

Sprint 3 can close on an owner-approved subset when:

- the submitted subset is made only of real products intended for the initial launch;
- the CEO confirms that the subset is complete for the intended initial launch;
- every included product is complete enough for validation/configuration;
- missing products are intentionally deferred rather than accidentally omitted.

Additional products may be added after Sprint 3 without reopening the WooCommerce foundation, subject to the normal catalog validation/change controls.

## What to provide for each included product

- Product name — English
- Product name — Japanese
- Product description — English
- Product description — Japanese
- Selling price in JPY
- Category
- Size / relevant variation information
- Pickup eligibility
- Delivery eligibility
- Temperature handling: chilled / frozen / other applicable mode
- Yamato shipping class or package-size information where delivery applies
- Inventory / availability rule
- Approved product image(s), with one clearly identified primary image
- Any product-specific ordering, lead-time, cancellation, seasonal or limited-availability condition

A final SKU may be provided by the owner or assigned during controlled catalog preparation, but each launch product must have a unique deterministic SKU before configuration is accepted.

## Category and media handoff

Only categories needed by the Initial Launch Catalog V1 subset need to be finalized now. Each included product must reference an approved category and approved media. Images must be owner-approved/verified sources; fixture, historical test, builder-test or placeholder media cannot satisfy catalog readiness.

## Owner confirmation required with the handoff

Confirm all of the following:

- **This is the Initial Launch Catalog V1 subset.**
- **The subset is complete for the products I intend to offer at initial launch.**
- **Products not included are intentionally deferred and may be added later.**
- **The product information, prices, categories and images supplied for this subset are approved.**

## What approval of the catalog does NOT authorize

Catalog approval does not by itself authorize:

- WooCommerce production writes;
- public publication;
- DNS/domain cutover;
- real KOMOJU payment execution;
- automatic production execution.

Those remain separate governed gates.

## Downstream flow after owner handoff

1. Transform the owner information into the canonical catalog package.
2. Validate the package and the Initial Launch Catalog V1 scope.
3. Compare it with a read-only WooCommerce catalog snapshot.
4. Produce a dry-run create/update/no-op plan; no automatic deletion.
5. Review the plan under the existing authority boundary.
6. Only after a separately authorized configuration gate, make the required preproduction catalog available.
7. Run the GET-only catalog probe.
8. Run the guarded non-transactional final-screen capture only when a real launch product is available for the disposable QA cart.

**Current authority remains fail-closed.**

# Sprint 4 — Customer Experience Exit-Readiness Checkpoint

**Date:** 2026-09-12  
**Repository:** `phireij/phil-ai-os-platform`  
**Engineering focus:** Sprint 4 — Customer Experience

This checkpoint records bounded Sprint 4 engineering evidence only. It does not close Sprint 3, authorize production activation, or grant WooCommerce, payment, SMS, inventory, DNS, or order-creation authority.

## Program position

- Sprint 3 — WooCommerce Foundation remains open and is currently constrained mainly by owner/external decisions and evidence.
- At the owner's direction, active owner-independent engineering has shifted to Sprint 4 while Sprint 3 remains parked behind those gates.
- Sprint 4 work remains pre-production and non-authorizing.
- The temporary branded storefront preview is a visual checkpoint only; the owner has parked further manual preview uploads for now.

## Sprint 4 exit-readiness evidence

The customer-experience implementation already contains automated coverage for:

- mobile-first layout, narrow-screen behavior, accessibility, focus recovery, and mobile performance;
- bilingual English/Japanese customer-facing state and navigation;
- product browse/detail behavior and product-media fallback/resilience;
- cart selection, quantity controls, recovery, locale continuity, and session recovery;
- checkout readiness, fulfillment selection, customer guidance, final-review continuity, and blocked-state behavior;
- PWA/offline behavior and connectivity/degraded-status handling;
- Quick Pickup bounded handoff behavior;
- technical SEO helpers and product structured data;
- inert KOMOJU handoff contracts with no live payment authority;
- confirmation-preview safety boundaries and explicit prevention of order submission.

## End-to-end synthetic smoke

This checkpoint adds an explicit fixture-only end-to-end customer journey that composes the existing Sprint 4 contracts rather than testing them only in isolation.

The smoke exercises both English and Japanese and proves two bounded paths:

1. **Ready path** — catalog card -> product detail -> multi-item cart -> checkout -> readiness GREEN -> inert KOMOJU handoff.
2. **Blocked path** — out-of-stock product -> checkout -> inventory blocker -> payment handoff refused.

The ready path uses only the synthetic fixture catalog and produces a JPY total from two synthetic in-stock products. The blocked path uses the synthetic out-of-stock product. No production catalog fact is introduced by this test.

The smoke is required to remain fail-closed with all of the following false:

- network call performed;
- mutation authority;
- production authority change;
- order creation authority;
- payment execution authority; and
- live payment mode authority.

The existing Sprint 4 CI automatically runs `apps/customer-experience/tests/*.test.mjs`, so the new end-to-end synthetic journey test is part of the normal Sprint 4 regression gate.

## What this checkpoint does not prove

This checkpoint does **not** claim:

- production browser/device acceptance;
- live WooCommerce catalog readiness;
- live KOMOJU connection or payment execution;
- live order creation;
- live SMS delivery;
- production Quick Pickup activation;
- production inventory synchronization;
- final owner acceptance of the branded storefront; or
- final Initial Launch Catalog V1 approval.

Those remain governed by their existing sprint, owner, external-provider, and production-activation gates.

## Continuation rule

Continue Sprint 4 only with material customer-experience or integration-readiness improvements. Do not manufacture cosmetic activity, bypass Sprint 3 owner gates, or treat pre-production evidence as launch authority.

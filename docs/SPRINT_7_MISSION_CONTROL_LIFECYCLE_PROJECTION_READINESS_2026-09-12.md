# Sprint 7 — Mission Control Lifecycle Projection Readiness

Date: 2026-09-12  
Status: BOUNDED READ-ONLY PROJECTION READY / LIVE ENDPOINT WIRING NOT AUTHORIZED

## Purpose

Advance the V1 Definition of Done item requiring Mission Control to expose lifecycle/result status without making Mission Control writable or enabling live execution.

## Bounded capability

`build_mission_control_lifecycle_projection` combines the existing read-only Operations Hub workload dashboard with the append-only Automation Hub audit read model and produces a privacy-preserving status projection suitable for a future Mission Control read endpoint/UI.

The projection exposes:

- channel event count
- extracted task count and approval workload
- pending staff order reviews
- pending quote approvals
- pending owner-review packets
- automation audit stage counts
- one latest stage/outcome summary per lifecycle correlation ID
- whether evidence remains simulation-only

The projection deliberately excludes customer text, custom notes, reference-image names and reply-draft text.

## Safety boundary

The projection requires both source models to remain read-only and fails closed on any execution, reply or mutation authority expansion. It outputs:

- `mission_control_mode=read_only`
- `execution_authorized=false`
- `channel_reply_authorized=false`
- `network_dispatch_authorized=false`
- WooCommerce/order/payment/SMS/inventory/publication/mutation authority all false
- `authority_effect=none`

## Evidence

- runtime: `apps/operations-hub/src/operations_hub/mission_control_projection.py`
- tests: `apps/operations-hub/tests/test_mission_control_projection.py`
- contract: `contracts/operations/mission-control-lifecycle-projection.schema.json`

## Remaining gate

This slice does **not** claim that the live Control API or browser Mission Control currently serves this projection. Wiring the projection into a live Mission Control endpoint/UI remains a separate controlled integration step and must preserve the existing read-only Mission Control boundary until explicitly authorized.

No production authority is changed by this readiness work.

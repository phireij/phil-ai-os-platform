# AO-1 — Project State and Evidence Reconciliation Contract

**Status:** IMPLEMENTATION PREP / A0-INERT  
**Authority effect:** none

AO-1 turns the Phase 0 registry into an evidence-backed project-state layer. It does not execute project work.

## Rules

1. A project state is a materialized read model, not an authority source.
2. Every repository/deployment claim must have evidence provenance and observation time.
3. Stale evidence is not silently promoted to current.
4. Missing evidence produces `unknown`, not GREEN.
5. Project adapters may read external systems but may not mutate them under A0.
6. Reconciliation must be deterministic and idempotent for the same evidence set.
7. Mission Control consumes this layer read-only.
8. Queue/selector/orchestrator execution remains out of scope until later AO phases.

## Canonical state

The v1 schema is stored at `ops/project-state/project-state.v1.schema.json`.

The normalized state deliberately separates:
- objective/milestone;
- overall status;
- repository state;
- deployment state;
- completed/WIP/queue/blockers;
- approvals;
- agent activity;
- next actions;
- evidence provenance/freshness;
- active authority ceiling.

## Adapter contract

An adapter returns observations only. Each observation has:
- project identity;
- source kind;
- immutable or reproducible source reference;
- observed timestamp;
- parsed facts;
- freshness classification.

The reconciler is responsible for deriving the normalized state from those observations. Adapters must not decide authority or execute actions.

## Fail-closed status

A state may be GREEN only when all fields required by its milestone have sufficiently fresh evidence. Otherwise it is YELLOW, RED, or UNKNOWN according to explicit rules. No optimistic default is allowed.

## Initial implementation order

1. Phil AI OS GitHub/repository adapter.
2. Ruby repository/readiness adapter.
3. KCFC GitHub/staging read-only adapter.
4. Materialized master multi-project read model.
5. Mission Control projection.

All five remain read-only/A0 until a separately authorized phase changes that boundary.

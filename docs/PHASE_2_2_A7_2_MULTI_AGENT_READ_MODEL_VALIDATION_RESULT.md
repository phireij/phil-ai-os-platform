# Phil AI OS Platform — Phase 2.2 A7.2 Multi-Agent Read Model Validation Result

**Phase:** 2.2 A7.2 — Multi-Agent Read Model Contract + Isolated Validation  
**Status:** GREEN / COMPLETE  
**Date:** 2026-08-28  
**Contract:** `docs/PHASE_2_2_A7_2_MULTI_AGENT_READ_MODEL_CONTRACT.md`  
**Validator:** `scripts/phase2_2_a7_2_multi_agent_read_model_validator.py`  
**Corrected validation run:** `33147554800`  
**Corrected job:** `98771843542`  
**Evidence artifact:** `phase-2-2-a7-2-isolated-read-model-validation` (`9676358320`)  
**Artifact digest:** `sha256:b47a0d5d6f9ab7dc4e86838191db685181a50d3e7af9e3d93281205c9c96d6c7`

## Decision

A7.2 is GREEN. The `2.2-a7.v1` read-model contract correctly projects two registered agents, identity-specific presence, durable workload ownership, accepted handoff history, registry precedence, and fail-closed evidence completeness without introducing Mission Control authority.

## Validated semantics

The isolated validator proved:

```text
schema=2.2-a7.v1
governed_transfer_reconciliation=verified
registry_precedence=verified
fresh_disabled_specialist=unassignable
terminal_handoff_history=visible_inactive
specialist_active_workload=0
missing_identity_evidence=fail_closed
unproven_ownership_conflict=indeterminate
secret_exclusion=verified
mission_control_authority=read_only_observer
```

Marker:

`PHIL_AI_OS_PHASE_2_2_A7_2_ISOLATED_READ_MODEL_CONTRACT_OK`

## Ownership-transfer correction

The first validator draft treated any task with more than one historical assignee as a conflict. That was too strict for the legitimate A6.8 handoff sequence, where ownership moves from Hermes to the specialist through an accepted, correlated handoff.

The validator was corrected so that a sequential source -> target assignment transition is considered legal only when a matching accepted handoff proves that exact task/source/target transition. A multi-owner transition without such evidence remains conflicting and projects `indeterminate` for an otherwise eligible worker.

This correction strengthens, rather than weakens, the contract: ownership transitions require durable handoff evidence instead of being accepted merely because multiple assignment rows exist.

## Registry precedence proof

The contract correctly preserves:

- `enabled=false` or `assignable=false` => `unassignable`;
- fresh presence cannot override disabled/non-assignable registry state;
- authority ceiling is reported as a ceiling and never as a grant;
- readiness has `grants_authority=false`.

Thus the fresh signed specialist remains `unassignable` after A6.8.

## Presence proof

The contract requires:

- Hermes identity through authenticated Control API round-trip presence evidence;
- specialist identity through dedicated signed evidence;
- fresh <=120 seconds, stale 121–300, offline >300;
- invalid/missing identity evidence => incomplete/unknown and fail closed.

## Workload and handoff proof

The validator proved:

- lifecycle ownership persists across later lifecycle rows that omit `assigned_agent_id`;
- terminal tasks do not count as active workload;
- the completed A6.8 accepted handoff remains visible historically;
- completed handoff ownership projects `active_ownership=false`;
- specialist active workload returns to zero;
- unproven conflicting ownership makes workload evidence incomplete.

## Secret exclusion

The contract excludes reusable credentials and secret material from the Mission Control projection, including bearer tokens, provider keys, private keys, raw authorization headers, and reusable approval credentials.

## Validation workflow correction

The initial validation workflow used `python | tee` without `pipefail`, which could mask a validator assertion failure behind `tee`'s exit status. The workflow was corrected to use `set -euo pipefail` and to upload evidence with `if: always()`.

The canonical result is the corrected run `33147554800` listed above.

## Gate decision

**A7.2: GREEN / COMPLETE.** Proceed to A7.3 production preflight using the read-only production candidate against live data without installing it.

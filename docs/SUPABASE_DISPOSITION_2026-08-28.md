# Phil AI OS Platform — Supabase Disposition

**Date:** 2026-08-28  
**Decision:** **DEFER FROM CORE V1 CRITICAL PATH**

## Decision

Supabase will not be introduced as a required Core V1 datastore or Sprint 3 dependency.

The existing durable SQLite control-plane database behind the Control API remains the canonical operational system of record for Core V1.

## Rationale

The current control-plane datastore already has:

- durable persistence;
- scheduled backups;
- backup freshness monitoring;
- backup self-heal;
- isolated restore validation;
- rollback discipline;
- centralized access through the Control API.

Introducing Supabase now would add:

- a second external identity/credential surface;
- synchronization and consistency complexity;
- risk of dual-system-of-record ambiguity;
- new operational dependencies during the accelerated V1 schedule;
- limited immediate benefit relative to the proven control-plane database.

## Future role

This is a deferral, not a permanent rejection.

Supabase may be reconsidered after V1 or when a clear requirement exists for capabilities such as:

- shared/multi-node data access;
- reporting/analytics separation;
- realtime data distribution;
- read replicas or downstream synchronization;
- a justified external application data plane.

If adopted later, its role must be explicitly defined so it does not silently replace Control API authority.

## Governance boundary

No Supabase production credentials, connectivity, schema deployment, data synchronization, or authority are approved by this disposition.

Any future production use requires a separate architecture and production activation gate.

`PHIL_AI_OS_SUPABASE_DEFERRED_FROM_CORE_V1`

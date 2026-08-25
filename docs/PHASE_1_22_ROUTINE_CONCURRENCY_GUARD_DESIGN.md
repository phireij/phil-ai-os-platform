# Phase 1.22 — Routine Concurrency Guard Design

Status: **DESIGNED — IMPLEMENTATION NOT YET ACTIVATED**  
Date: 2026-08-26

## Evidence

GitHub Actions run `32910386113` — Phase 1.22 Routine Concurrency Guard Discovery — completed successfully.

Discovery verified:

- Control API health is OK.
- Production allowlist remains exactly `general`.
- Routed execution is enabled.
- No concurrency/semaphore/lock environment control is currently configured.
- Routed execution is implemented in `/app/app.py` at `routed_execute()`.
- `/v1/execute` calls `routed_execute()`.
- The Control API container runs `python /app/app.py` as a single container process entrypoint.
- No existing deterministic routine concurrency guard was discovered.
- No provider call, production change, or routine activation occurred during discovery.

## Design objective

Enforce the Phase 1.22 contract requirement that at most **one `routine` execution may be in flight at a time**, while leaving `general` execution behavior unchanged.

The guard must fail closed, must not create a direct-provider bypass, and must always release after success or failure.

## Selected design

Implement a process-local non-blocking mutex dedicated to the `routine` task class at the Control API execution boundary.

Because the currently deployed Control API topology is a single Python application process in one container, a process-local `threading.Lock` is sufficient for the initial bounded Phase 1.22 activation scope. The guard is deliberately placed inside the Control API rather than in Hermes or provider adapters so every routed routine execution traverses the same enforcement point.

### Required behavior

1. Existing allowlist, kill-switch, request-size, budget, routing and approval checks remain authoritative.
2. Only after the request is classified/validated as `routine`, attempt to acquire the routine lock with `blocking=False`.
3. If acquisition fails, return a deterministic fail-closed response such as `routine_execution_busy` without invoking any provider and without consuming a new provider budget event.
4. If acquisition succeeds, hold the lock across the provider-execution critical section.
5. Release the lock in a `finally` block so provider errors and unexpected exceptions cannot strand the guard.
6. `general` executions do not acquire this routine-specific lock.
7. The guard does not itself enable `routine`; production remains `general` only until a later approved activation.

## Audit requirement

A rejected concurrent routine attempt should be observable through the execution/audit surface with a stable reason/status (`routine_execution_busy`) where the current audit architecture permits recording pre-provider rejection evidence.

No secret, prompt content, or provider credential should be added to logs merely for concurrency enforcement.

## Validation plan

Before production routine activation, validate without provider calls:

- first simulated routine holder acquires the guard;
- second concurrent routine attempt fails closed immediately;
- rejection reason is deterministic;
- lock is released after normal completion;
- lock is released after raised exception;
- a subsequent routine attempt can acquire after release;
- `general` path remains unaffected;
- production allowlist remains `general` during implementation validation.

## Scale boundary

This process-local mutex is valid only while the Control API remains a single-process/single-instance execution authority.

Before adding multiple workers, replicas, or another Control API execution instance, replace or augment it with a cross-process atomic lease/lock (for example, a transactional SQLite lease appropriate to the deployment, or another durable coordination primitive). Scaling the Control API without revisiting this guard is prohibited by this contract.

## Rollback

The implementation must be isolated enough to remove the routine mutex and restore the previous `routed_execute()` behavior without changing approval records, provider credentials, or the persistent `general` production allowlist.

## Next action

Implement the guard in the deployed Control API source through a controlled workflow, restart only the Control API if required, and run a no-provider concurrency validation. Do **not** add `routine` to the production allowlist.

`PHIL_AI_OS_PHASE_1_22_ROUTINE_CONCURRENCY_GUARD_DESIGN_DEFINED`

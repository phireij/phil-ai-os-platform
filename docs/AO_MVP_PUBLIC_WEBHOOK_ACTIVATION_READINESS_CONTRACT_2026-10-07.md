# AO-MVP Public Webhook Activation Readiness Contract

Status: PLANNING ONLY — ACTIVATION NOT AUTHORIZED

Authority effect: none.

## Durable predecessor checkpoint

This phase is downstream of the completed, approved private isolated VPS A1 runtime checkpoint.

Required inherited invariants:
- `activation_authorized=true` for the approved private isolated VPS scope only;
- `production_mutation_authorized=false`;
- `authority_effect=none`;
- A1 denylist remains enforced;
- rollback remains fail-closed;
- no production credentials are required or introduced.

This document MUST NOT reinterpret private A1 activation as authorization for public ingress.

## Explicitly prohibited before a separate CEO approval

No implementation step may:
- add or reuse a public hostname;
- create or modify DNS;
- add or modify public routes, reverse-proxy routes, firewall openings, or exposed ports;
- reuse the Hermes hostname, router, ingress identity, credentials, or authority;
- introduce production credentials, production data, customer systems, payments, Twilio, or live messaging;
- mutate production inventory, slots, orders, customer data, or other production state;
- expand A1 authority or infer approval from prose, prior A1 approval, repository state, or deployment presence.

## Pre-activation work that is allowed

Repository-only preparation may define and test:
1. a dedicated public-webhook ingress identity and isolation model;
2. request authentication/signature verification contracts;
3. replay protection, timestamp/nonce bounds, and idempotency;
4. strict payload size/content-type/schema validation;
5. rate-limit and abuse/flood behavior;
6. secret redaction and no-payload logging rules;
7. fail-closed dependency behavior;
8. health/readiness semantics that do not expose sensitive internals;
9. a synthetic-only end-to-end harness with no network exposure;
10. rollback that removes ingress reachability and leaves private A1 state intact;
11. evidence schema and exact-revision validation;
12. an explicit activation approval record separate from A1.

## Required activation evidence

A future public-webhook activation is NOT READY unless all items are GREEN and fresh:
- dedicated hostname selected and proven not to be Hermes reuse;
- DNS change plan reviewed but not applied;
- ingress/route/port change plan reviewed but not applied;
- TLS ownership and renewal plan defined;
- authentication/signature scheme validated with synthetic secrets;
- replay and duplicate-delivery tests pass;
- malformed, oversized, stale, unauthenticated, and unsupported requests fail closed;
- rate-limit/abuse tests pass;
- logs contain no secrets, customer payloads, or sensitive headers;
- webhook handler has no production mutation capability under this phase;
- public ingress cannot reach Hermes authority surfaces;
- rollback drill is defined and independently testable;
- exact immutable revision and CI evidence are GREEN;
- activation record explicitly states `public_webhook_activation_authorized=true`;
- activation record continues to state `production_mutation_authorized=false` and `authority_effect=none`.

## Approval boundary

The future approval must be explicit and phase-specific. A1 activation, VPS access, prior deployment approval, or approval to prepare this contract do not satisfy it.

Until that explicit approval exists:
`public_webhook_activation_authorized=false`.

## Future activation sequence after approval

Only after explicit approval:
1. revalidate exact revision and evidence freshness;
2. verify the dedicated hostname/DNS/route plan matches the approved evidence;
3. apply the minimum isolated ingress change;
4. verify TLS and authentication;
5. send synthetic canary requests only;
6. verify denylist and zero production mutation;
7. capture evidence;
8. rollback immediately on any unknown or failed invariant.

Any ambiguity or partial failure means fail closed and restore the pre-public-ingress state.

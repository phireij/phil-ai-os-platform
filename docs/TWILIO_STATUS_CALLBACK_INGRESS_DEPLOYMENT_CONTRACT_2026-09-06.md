# Ruby’s Cake Delights — Twilio Status Callback Ingress Deployment Contract

Date: 2026-09-06  
Status: PREPARED / NON-DEPLOYED / FAIL-CLOSED  
Scope: Ruby Transactional SMS delivery-status callback only

## Purpose

Define the production ingress and runtime contract required to expose the already implemented signed Twilio delivery-status HTTP boundary without deploying it yet.

This document is engineering preparation only. It does **not** authorize or perform a Traefik change, Control API deployment, DNS change, Twilio console mutation, SMS send, WooCommerce mutation, payment execution, or production cutover.

## Current discovered state

Read-only workflow run `33995788012` established:

- one active Traefik candidate;
- the primary Control API is healthy locally on loopback port `4870`;
- existing HTTPS/TLS ingress uses the `websecure` entrypoint and a configured certificate resolver;
- the primary Control API already has path-scoped public routes for approval and Mission Control;
- the separate operator proxy has its own path-scoped route;
- no current router for `/v1/webhooks/twilio/sms-status` was discovered;
- no approved file-provider hint for that callback path was discovered.

Canonical structured evidence: `ops/readiness/ruby-twilio-ingress-discovery-2026-09-06.json`.

## Required callback path

The application boundary is fixed at:

`POST /v1/webhooks/twilio/sms-status`

Do not silently rewrite this path and do not place it behind an unrelated existing path prefix unless the application contract is deliberately changed and retested first.

## Candidate Traefik contract — not activated

A future governed production change may add a dedicated router on the already established Phil AI OS HTTPS host with these properties:

- rule: the existing approved Phil AI OS host **and exact callback path** `/v1/webhooks/twilio/sms-status`;
- entrypoint: `websecure`;
- TLS enabled under the existing certificate-resolver pattern;
- service target: the primary Control API service on port `4870`;
- no broad catch-all path;
- no redirect to a different canonical URL after Twilio signs the request;
- no middleware that mutates form fields or reconstructs signature material;
- no public exposure of unrelated Control API routes.

The public hostname is deliberately not duplicated in this document. Deployment automation must resolve it from the approved live ingress configuration rather than inventing or hard-coding a new host.

## Canonical callback URL rule

Runtime must receive one explicit configuration value:

`RUBY_TWILIO_STATUS_CALLBACK_URL`

Requirements:

1. HTTPS only.
2. Exact path `/v1/webhooks/twilio/sms-status`.
3. No fragment.
4. Must exactly match the externally visible URL Twilio signs.
5. Must not be reconstructed from untrusted `Host` or `X-Forwarded-*` headers.
6. Must not be inferred from the approval, Mission Control, or operator routes.

The Account Auth Token used for signature validation remains separate:

`RUBY_TWILIO_AUTH_TOKEN`

Outbound Twilio REST authentication continues to use the restricted API key SID/secret and must not be changed by callback deployment.

## Application boundary requirements

The deployed Control API route must delegate to the existing `TwilioStatusHttpBoundary` contract and preserve all current safety properties:

- only `POST` on the exact callback path;
- maximum body size `8192` bytes;
- `application/x-www-form-urlencoded` only;
- `X-Twilio-Signature` required;
- Account Auth Token validation against the explicit canonical URL;
- malformed bodies, duplicate form fields, missing signature, bad signature, invalid message SID/status, wrong path, wrong content type, and oversized body fail closed;
- valid callback returns HTTP `204`;
- persistence, if wired, receives only the redacted projection;
- raw recipient/sender values are not persisted by this boundary;
- Message SID audit projection remains hashed;
- callback has `authority_effect=none`;
- no automatic retry;
- no SMS send;
- no WooCommerce mutation;
- no payment-state mutation.

## Deployment prerequisites

Before any production ingress/runtime mutation, all of the following must be independently checked:

- fresh backup/recovery state is within the required cutover window;
- host Control API source and live container source match the expected baseline;
- candidate code has passed isolated syntax/unit/contract tests;
- current A0/general/Hermes-only governance state is preserved;
- `RUBY_TWILIO_AUTH_TOKEN` presence is verified inside the approved secret boundary without printing the value;
- `RUBY_TWILIO_STATUS_CALLBACK_URL` is resolved from the approved public ingress host and exact callback path without printing secrets;
- Traefik change is narrowly scoped to the callback route;
- rollback removes only the new callback route/runtime wiring and restores the prior Control API image/source/config;
- no DNS change is required unless separately approved;
- no SMS send is required to validate initial route deployment.

## Safe validation sequence after a separately governed deployment

1. Verify local Control API health/readiness.
2. Verify the new route exists and existing approval/Mission Control/operator routes are unchanged.
3. Send a deliberately unsigned or invalid-signature callback-shaped request and confirm fail-closed rejection. This is not a Twilio send.
4. Execute a locally generated signed callback test against the exact canonical URL using a non-production synthetic `MessageSid` shape, without recording raw secrets.
5. Confirm valid callback returns `204` and only redacted/non-authorizing evidence is produced.
6. Re-run existing Control API, Mission Control, WooCommerce, and integrated readiness regressions.
7. Only after route/runtime verification is GREEN may Twilio console delivery-status callback configuration be considered under its separate readiness gate.
8. The CEO-approved one controlled handset SMS remains downstream of final template, recipient, callback, and no-send provider preflight readiness.

## Rollback contract

Rollback must be possible without affecting unrelated public routes:

- remove/disable only the dedicated Twilio callback router;
- restore the prior Control API source/image/runtime configuration;
- remove/disable only the callback-specific runtime secret reference if it was introduced solely for this route;
- verify approval, Mission Control, and operator routes still behave exactly as before;
- verify Control API `/healthz` and `/readyz`;
- do not delete Twilio account/service/sender configuration as part of infrastructure rollback.

## Authority statement

Current state remains:

- callback ingress deployed: **false**;
- canonical callback URL runtime configured: **false**;
- Twilio delivery-status callback verified: **false**;
- live SMS authorized by readiness: **false**;
- unrestricted SMS authorized: **false**;
- automatic retry authorized: **false**;
- production WooCommerce mutation authorized by this contract: **false**;
- payment execution authorized by this contract: **false**;
- DNS/public cutover authorized by this contract: **false**.

Decision: **INGRESS_CONTRACT_PREPARED_NON_DEPLOYED_PRODUCTION_CALLBACK_REMAINS_FAIL_CLOSED**

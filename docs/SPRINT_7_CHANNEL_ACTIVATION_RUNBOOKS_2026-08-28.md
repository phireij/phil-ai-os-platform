# Sprint 7 — External Channel Activation Runbooks

Date: 2026-08-28
Status: PREPARATION ONLY / LIVE CHANNEL ACTIVATION NOT AUTHORIZED

## Baseline

Sprint 5 proved synthetic normalization, idempotency, intent/confidence classification, governance routing and mock-only provider adapters for Facebook, Instagram, Telegram, WhatsApp and Google Business. It explicitly did **not** authorize live credentials, connectivity, production webhooks/polling, outbound replies or customer/account mutations.

All five channels remain subject to the current platform baseline:

- autonomy **A0**;
- `general` task class only;
- Hermes-only bounded routing;
- specialists disabled;
- Mission Control read-only;
- live channel connectivity false;
- outbound replies false;
- customer/account mutations false.

## Common activation sequence

For each channel, use the following sequence and stop at the highest explicitly approved level:

1. **Capability verification** — confirm the platform's current supported API/webhook capabilities, authentication model, permissions/scopes and policy requirements at activation time.
2. **Identity review** — identify the exact business/app/bot identity; do not reuse an unrelated identity merely because credentials already exist.
3. **Least privilege** — request only the minimum permissions needed for the approved inbound/read scope.
4. **Secret handling** — store credentials/signing secrets only in the approved runtime secret location; never GitHub, fixtures or logs.
5. **Ingress verification** — validate signatures/tokens/challenges or equivalent authenticity controls supported by the channel.
6. **Read-only canary** — ingest a narrow event/message/review sample into Operations Hub while outbound reply/write remains disabled.
7. **Idempotency/replay proof** — duplicate delivery must reconcile safely without duplicate work.
8. **Governance proof** — complaint/public-review/low-confidence cases must route to review/approval according to policy.
9. **Monitoring** — record event volume, error rate, auth failures and malformed/duplicate behavior.
10. **Rollback proof** — confirm the webhook/app/token can be disabled/revoked to return the channel to disconnected/manual handling.
11. **Separate write gate** — only after inbound/read evidence is GREEN may outbound reply/write be proposed for explicit approval.

## Facebook

### Inbound/read activation prerequisites

- approved Facebook business/app integration identity;
- current platform permissions/scopes verified before configuration;
- verified ingress/authenticity mechanism;
- synthetic Facebook Operations tests remain GREEN;
- idempotency/replay and approval routing GREEN;
- disable/revoke path documented.

### Outbound/write gate

Reply/post/account-write capabilities remain disabled until separately approved, canary-tested and auditable.

### Abort

Disable the integration if identity/scope is broader than approved, authenticity validation fails, duplicate storms appear, or account/customer writes occur unexpectedly.

## Instagram

### Inbound/read activation prerequisites

- approved Instagram/business integration identity linked only as required by the current platform model;
- current permissions/scopes verified at activation time;
- verified ingress/authenticity mechanism;
- synthetic Instagram normalization and replay tests GREEN;
- disable/revoke path documented.

### Outbound/write gate

Replies/posts/writes remain a separate authority decision.

### Abort

Return to disconnected/manual handling on auth, scope, duplicate, routing or unintended-write anomalies.

## Telegram

Phil AI OS already has historical Telegram usage for control-plane approval/notification workflows. **That does not grant Operations Hub Telegram channel authority.** Existing approval-channel credentials/identity must not be silently repurposed for broader customer Operations traffic.

### Inbound/read activation prerequisites

- decide whether Operations uses a separate bot/identity or an explicitly reviewed extension of an existing identity;
- verify current bot/webhook/update behavior and scope at activation time;
- preserve control-plane approval isolation;
- synthetic Telegram Operations tests and replay protection GREEN;
- disable/revoke path documented.

### Outbound/write gate

Customer-facing replies or broader bot actions require a separate explicit gate even if the control-plane notifier is already operational.

## WhatsApp

### Inbound/read activation prerequisites

- approved business integration identity;
- current platform/API permissions and business policy prerequisites verified;
- ingress authenticity verification configured;
- synthetic WhatsApp normalization/replay tests GREEN;
- disable/revoke path documented.

### Outbound/write gate

Messages/templates/customer writes remain disabled until separately approved and validated.

### Abort

Disable integration for auth/signature failures, unexpected billing/message behavior, wrong-recipient risk, duplicate sends or permission drift.

## Google Business

Google Business capabilities and APIs can change over time; the exact supported review/message/business-profile integration path and permissions must be verified immediately before activation rather than frozen into this runbook.

### Inbound/read activation prerequisites

- approved Google Business integration identity;
- current supported capability/API and permissions verified at activation time;
- synthetic Google Business event normalization/review-routing tests GREEN;
- idempotency/replay controls GREEN;
- disable/revoke path documented.

### Outbound/write gate

Review replies or business-profile mutations remain separately gated and disabled by default.

## Launch blockers for any channel

Do not activate the affected channel if:

- the current supported API/capability cannot be verified;
- business/app/bot identity is ambiguous or broader than approved;
- secret storage or rotation/revocation is not ready;
- ingress authenticity cannot be validated;
- replay/idempotency tests regress;
- approval/review routing is not GREEN;
- rollback/disable path is unclear;
- outbound write/reply would be required before a separate write gate is approved.

## Explicit non-authorization

This document does not authorize live credentials, API/webhook connectivity, polling, outbound replies, posts, review replies, customer/account changes, specialist execution, higher autonomy, new task classes or Mission Control mutation authority.

`PHIL_AI_OS_SPRINT_7_CHANNEL_RUNBOOKS_READY_NOT_AUTHORIZED`

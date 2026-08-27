# Phase 2.1K K5 — Controlled Approved Execution Canary Result

Status: **GREEN**

Date: 2026-08-27

## Human authorization

The human operator explicitly approved the exact K4 canary through the secure Mission Control approval link before K5 execution.

- Approval ID: `apr_7a3594fc61d1467593181d1ca7a2d502`
- Canonical task ID: `tsk_e9694565de884bc9afa550d57db32426`
- Task class: `general`
- Decision state before execution: `approved`
- Decision actor recorded by the secure link: `mission-control-link`

## Controlled execution evidence

The exact approved task was submitted once through authenticated `POST /v1/execute` using the existing Hermes Control API credential boundary.

Observed result:

- HTTP status: `200`
- Execution status: `ok`
- Execution mode: `controlled`
- Classification: `general`
- Provider: `openai`
- Model: `gpt-5.6-terra`
- Route path: `primary`
- Compatibility check: `true`
- Expected/output text: `PHIL_AI_OS_ROUTED_EXECUTION_OK`
- Input tokens: `24`
- Output tokens: `13`
- Total tokens: `37`
- Estimated cost: `$0.00051`
- Response ID: `resp_0315bd7a8b32eac2016a902407d4ac87d0af2b1f3e70534fcf`

The approval was atomically consumed by `hermes` and the durable successful execution audit linked the exact approval ID and canonical task ID.

## Replay proof

A second request using the same approval ID was immediately attempted only to validate replay protection.

Observed result:

- HTTP status: `409`
- Execution status: `execution_approval_rejected`
- Approval status: `approval_already_consumed`
- Second provider call: **false**

Final durable audit proof showed:

- successful execution rows: `1`
- provider response rows: `1`
- replay rejection rows: `1`

The replay rejection row has no provider, response ID, or route path, proving rejection occurred before a second provider invocation.

`PHIL_AI_OS_PHASE_2_1K_K5_EXECUTION_AND_REPLAY_GREEN`

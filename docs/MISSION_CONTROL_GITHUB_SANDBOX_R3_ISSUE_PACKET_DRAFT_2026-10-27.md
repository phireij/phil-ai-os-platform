# Mission Control GitHub Sandbox R3 Issue Packet Draft — 2026-10-27

## Status and limit

This is an owner-approved **draft packet**, not an issued R3 approval and not
dispatch authority. It creates no issue, does not read a credential, and does
not request an installation token. The separate runtime ledger is deliberately
unwired, so this document cannot activate GitHub access.

At approval time, the packet is valid only for one issue attempt in the stated
repository. It expires 15 minutes after approval and cannot be reused, retried,
or repurposed.

## Fixed operation and content

| Field | Fixed value |
| --- | --- |
| Target repository | `phireij/mission-control-github-sandbox` |
| Operation | `create_labelled_issue` |
| Required existing label | `mission-control-sandbox-pilot` |
| Title | `Mission Control sandbox pilot - approval-gated verification` |
| Body | `This is a single, approval-gated Mission Control sandbox verification.` followed by a blank line and `It contains no customer, employee, payment, secret, production, or conversation data.` |
| Plan/content digest | `sha256:aa4bc99211c65d49364ce7df36c501d270637c12990b802e48b7829c73f98ffb` |

The digest is SHA-256 over canonical JSON with sorted keys and compact
separators for precisely the fixed repository, operation, label, title, and
body above. It intentionally excludes names, customer data, secrets, payment
data, raw conversation content, and any credential material.

## Approval-time evidence required

The system must create a fresh approval record only after all of the following
are independently true:

1. The CEO reauthentication is no older than five minutes.
2. The CEO supplies this exact typed confirmation:

   ```text
   CREATE ONE LABELLED SANDBOX ISSUE in phireij/mission-control-github-sandbox
   ```

3. The record has risk `R3`, this packet's digest, a new opaque approval ID,
   one 900-second lifetime, and an unconsumed/unrevoked state.
4. The 24-hour issue count is zero, the external-action budget and reservation
   are both `$0`, and no emergency stop is active.
5. The idempotency key is absent and will be bound to only this approval ID and
   digest.
6. The emergency-stop owner is **Phil B** as primary owner and temporary
   secondary owner under the approved single-person exception. The App
   installation suspend and uninstall controls remain available.

## Explicit non-authorization

Even a fully formed approval record must stop for review if the runtime ledger,
credential boundary, GitHub installation metadata, budget evidence,
idempotency evidence, or emergency-stop state is unavailable or differs from
this packet. The packet does not authorize title/body changes, comments,
labels, branches, merges, workflows, deployments, retries, deletion, or any
other GitHub action.

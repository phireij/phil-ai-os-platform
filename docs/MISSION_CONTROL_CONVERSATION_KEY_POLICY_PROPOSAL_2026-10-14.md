# Mission Control conversation key policy proposal

**Status:** proposed, inactive, and awaiting CEO approval. This document creates no key, secret, volume, credential, or deployment authority.

## Recommended ownership

- **Accountable owner:** CEO.
- **Runtime custodian:** the Mission Control host's root-only deployment boundary.
- **Recovery custodian:** CEO, using an existing private secret manager or encrypted offline vault selected by the CEO. No recovery material belongs in Git, chat, CI artifacts, application logs, or browser storage.

This keeps business accountability with the data owner while limiting the running service to a mounted read-only key file. GitHub Actions may coordinate a reviewed deployment but should not retain the master conversation key.

## Key lifecycle

1. Generate a random 256-bit master key on the Mission Control host through a separately approved guarded operation.
2. Store the runtime copy in a dedicated root-owned location and mount it read-only into only the CEO session container. The application user receives read access to the file and no access to Docker, Hermes, or other workload secrets.
3. Create one recovery copy under the CEO's selected private vault. Record only a non-secret key identifier and creation time in deployment evidence.
4. Rotate every 90 days and immediately after suspected disclosure, unauthorized file access, custodian change, or cryptographic incident.
5. Rotation must run offline: stop the conversation container, authenticate and decrypt the live state, deletion ledger, and unexpired backups with the prior key, re-encrypt them with the new key, verify quarantined outputs, then activate through a reviewed atomic swap.
6. Retain a retired key only while an unexpired backup still depends on it, for no longer than the approved 35-day backup window. Destroy both runtime and recovery copies after that dependency ends and record non-secret evidence.

## Failure rules

- Missing, malformed, weakly permissioned, symlinked, overlapping, or unreadable key paths fail startup closed.
- A lost runtime key must be restored only from the CEO-controlled recovery copy. Absence of a verified recovery copy blocks activation.
- Authentication or integrity failure blocks restore; operators must not bypass the check or export plaintext.
- Recovery and rotation produce quarantine outputs. Neither operation may overwrite live files or start the service.

## Approval needed before activation

The CEO must approve this ownership and 90-day rotation policy and identify the existing private secret manager or encrypted offline vault that will hold the recovery copy. No secret value or recovery artifact should be sent in chat.

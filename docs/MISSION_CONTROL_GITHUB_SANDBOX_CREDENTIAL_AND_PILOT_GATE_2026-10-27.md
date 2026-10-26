# Mission Control GitHub sandbox credential and pilot gate

**Recorded:** 2026-10-27 JST  
**Owner decision:** credential-handling and bounded-pilot design approved.  
**Authority effect:** none until a separate per-issue R3 approval is valid at
dispatch time.

## Purpose and scope

This gate describes the only permissible future use of the GitHub App **Mission
Control Sandbox Pilot**: create one pre-labelled issue in
`phireij/mission-control-github-sandbox`. It does not authorize a token request,
an issue, a retry, a comment, a close/reopen, a repository change, or any action
outside that repository.

The App remains installed on one selected repository with Metadata read and
Issues read/write. The prior source-only contract and validator remain inert and
cannot read a credential or contact GitHub.

## Credential boundary

1. The downloaded GitHub App private key is owner-managed secret material. It
   must never be pasted into chat, a terminal command line, source control,
   environment-variable value, browser storage, Mission Control records, logs,
   exceptions, or audit evidence.
2. Before any runtime is built, the owner must place the file in a dedicated
   root-owned secret directory on the approved isolated host. The proposed path
   is `/opt/phil-ai-os-platform/mission-control/secrets/github-sandbox-pilot.pem`.
   The directory must be mode `0700`; the file must be root-owned and mode
   `0400`. The file path—not its contents—may be configured.
3. A dedicated, non-browser worker may receive the path through a narrowly
   named configuration reference. No HTTP route, UI, workflow variable, or
   general-purpose task runner may receive the key or key path.
4. The worker may hold key material only in process memory for a single
   preflight/dispatch attempt. It must clear references on every exit and never
   include secret-derived data in exceptions or audit fields.
5. The worker must mint an RS256 GitHub App JWT only after the R3 preflight has
   passed. Its `iat` must tolerate clock skew and its `exp` must be no more than
   ten minutes ahead, per [GitHub's JWT guidance](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app).
6. It may exchange that JWT for one installation token, restricted to the one
   installed repository and the minimal issue permission. GitHub documents that
   installation tokens cannot exceed the App installation's repository/permission
   access and expire after one hour; the worker must retain one only for its
   single attempt and discard it immediately afterward. See [GitHub's installation-token guidance](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).

## Required preflight

Every potential dispatch must fail closed unless all of the following are true
immediately before it mints a JWT:

1. The App identity, installation, selected-repository list, and effective
   permission response match the one approved sandbox target exactly.
2. The repository is private, has no configured webhook for this pilot, and
   contains the pre-existing `mission-control-sandbox-pilot` label.
3. The plan is immutable and hashes to the approval packet's `plan_digest`.
   It names exactly one operation, `create_labelled_issue`, in the pinned
   repository and does not contain personal, customer, secret, payment, or
   production content.
4. A current CEO R3 decision includes a typed confirmation of the exact
   repository and operation, is no older than five minutes at confirmation, has
   a 15-minute lifetime, is unrevoked, and has never been consumed.
5. The single-person emergency-stop exception is still valid, or a distinct
   secondary operator is present. The App installation's manual **Suspend** and
   **Uninstall** controls must remain accessible to the emergency-stop owner.
6. The $0 external-action budget and one-issue/24-hour pilot limit have an
   available reservation. Unknown or unavailable budget evidence blocks.
7. A scoped idempotency record does not show a completed, in-flight, or
   ambiguous attempt for the plan digest and issue-content digest.

## Bounded live-pilot policy

| Control | Pilot value |
| --- | --- |
| Target | `phireij/mission-control-github-sandbox` only |
| Operation | Create one issue only; no comment, edit, close, reopen, label creation, branch, merge, release, workflow, deployment, or settings action |
| Label | Use only the pre-existing `mission-control-sandbox-pilot` label |
| Rate | One issue in any rolling 24-hour window; one total dispatch attempt per approval |
| Content | Static non-sensitive title/body template plus plan/audit digests only; no customer, employee, secret, payment, Google, or raw conversation data |
| Approval | R3 typed confirmation, current reauthentication, one immutable plan digest, 15-minute expiry, single use |
| Budget | $0; reservation and reconciliation are still required |
| Verification | Read only the pinned repository to confirm one issue with the expected label and content digest |
| Uncertain outcome | `stopped_for_review`; no automatic retry, deletion, close, rollback, or compensating action |

The first live title/body template must be attached to the exact R3 approval
packet before dispatch. This gate deliberately does not pre-authorize any issue
content.

## Audit and emergency stop

The audit record may contain only opaque correlation IDs, plan/content digests,
App/installation references, selected repository reference, issuance and expiry
timestamps, idempotency key, redacted response classification, and outcome. It
must not contain the private key, JWT, installation token, authorization header,
raw issue body, or raw API response.

Either designated emergency-stop owner may suspend or uninstall the App
installation. A stop blocks new token issuance and dispatch immediately; it does
not delete the issue or trigger a compensating operation. Restart requires CEO
approval and a recorded safety review. The current single-person exception is
not a substitute for the planned independent secondary operator.

## Remaining implementation and activation gates

1. The owner places the already downloaded key at the dedicated host path with
   the stated ownership and modes, without disclosing its contents.
2. A source-only credential-boundary implementation and tests prove file-mode
   rejection, redaction, JWT lifetime enforcement, installation/repository/
   permission pinning, single-use lease consumption, idempotency persistence,
   and all failure paths.
3. A read-only preflight and manual suspend/revoke rehearsal complete without
   issuing an installation token or creating an issue.
4. The CEO approves one exact R3 issue packet, including the static title/body,
   plan digest, target, timing, and emergency-stop owner.

Only step 4 authorizes one issue attempt. Until then, this is a source and
operating-design record, not live execution authority.

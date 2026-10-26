# Mission Control GitHub sandbox adapter readiness

**Recorded:** 2026-10-27 JST  
**Status:** Sandbox App provisioning and a configuration-only security review are
recorded; no adapter, token use, workflow, route, or issue-creation authority is
enabled.

## Current finding

The approval-gated foundation and the identity-only Google probe remain
non-authorizing. Repository review finds no GitHub credential-reading path,
GitHub client, or adapter activation workflow. The source-only validator now
enforces the exact future target-repository/operation/label request shape while
always returning a blocked preview. This is the correct posture until the
remaining implementation gates in the [credential and pilot gate](MISSION_CONTROL_GITHUB_SANDBOX_CREDENTIAL_AND_PILOT_GATE_2026-10-27.md)
are complete.

### External sandbox provisioning — 2026-10-27

- The owner-authorized private repository
  [`phireij/mission-control-github-sandbox`](https://github.com/phireij/mission-control-github-sandbox)
  now exists. Issues are enabled; Actions, projects, wiki, discussions, and
  downloads are disabled; no webhooks are configured; and the pre-created
  `mission-control-sandbox-pilot` label is the only label an eventual adapter
  may use.
- GitHub does not allow private-repository forking to be disabled on a
  user-owned account. The repository remains private and must be installation-
  pinned to a single App if a pilot is later approved.
- No GitHub organization is currently available to the owner account. A
  personal-account GitHub App cannot give the named secondary operator the
  required independent installation-stop authority. The approved temporary
  single-person exception therefore remains in force; a future organization
  migration with the CEO and Ruby Bombeo as owners is still required to restore
  independent dual control.

### GitHub App provisioning — 2026-10-27

- The owner authorized the personal-account GitHub App **Mission Control Sandbox
  Pilot**. GitHub's 34-character app-name limit required this approved shortened
  form of the requested name.
- The App is installed on exactly one repository:
  `phireij/mission-control-github-sandbox`. GitHub's installation review shows
  `Only select repositories` and one selected repository; it is not installed
  on current or future repositories generally.
- Repository permissions are limited to Metadata read (GitHub-mandatory) and
  Issues read/write. All other repository, organization, account, and enterprise
  permissions are no access. Webhooks, OAuth-on-install, Device Flow, setup URL,
  and event subscriptions are disabled or absent.
- A private key was generated and downloaded directly by GitHub to the
  owner-controlled browser environment. It was not opened, copied, logged, or
  stored in this repository, Mission Control records, or browser persistence by
  this work. No client secret was created.
- The installation has not been used: no installation token was requested, no
  workflow or adapter was deployed, and no sandbox issue was created.

### Temporary single-person emergency-stop exception — 2026-10-27

- The owner temporarily designates themself as both the CEO primary and the
  secondary emergency-stop operator. This is an explicit single-person
  exception, not independent dual control: it permits the owner to stop a
  future sandbox installation but does not satisfy the original separate-
  operator safeguard.
- The exception expires on 2026-11-26 JST or when a distinct technical operator
  is added, whichever occurs first. It did not itself authorize App provisioning
  or installation, and it does not authorize issue creation.

## Dedicated adapter security review — configuration result

**Review scope:** the provisioned App's visible configuration and the current
repository source tree. The review intentionally did not open the private key,
request an installation token, or call the GitHub API as the App.

**Result:** configuration minimization is **PASS**; adapter implementation and
live-pilot readiness are **BLOCKED**.

| Control | Result | Evidence / remaining requirement |
| --- | --- | --- |
| App permission minimization | PASS | Metadata read is mandatory; Issues read/write is the sole selected permission. |
| Installation target scope | PASS | GitHub shows one selected repository: `phireij/mission-control-github-sandbox`. |
| Webhook and user-token surface | PASS | Webhooks, OAuth-on-install, and Device Flow are off; no event subscriptions are selected. |
| Credential isolation | PASS for current posture | The key was not accessed by this work and no repository or Mission Control secret path exists. PR #654 adds an inert public-metadata validator for the proposed root-owned secret-file boundary; a credential-reading runtime still requires separate review. |
| Source-level target pinning | PASS for the inert request boundary | PR #651 adds a pure validator that rejects every repository, operation, or label except the exact allowlisted sandbox target and labelled issue creation. It always returns a blocked preview and has no token, network, or dispatch path. |
| Token non-disclosure | BLOCKED | No token path exists yet. The implementation must prevent private keys, JWTs, installation tokens, authorization headers, and raw API errors from entering logs, audit records, exceptions, or browser responses. |
| One-action lease and approval binding | BLOCKED | The inert Mission Control contracts exist, but no GitHub adapter validates a single-use, unexpired, plan-bound R3 lease. |
| Idempotency and ambiguous-result handling | BLOCKED | The implementation must persist a scoped idempotency key before dispatch, query only the pinned repository for recovery evidence, and stop for review on any uncertain outcome. |
| Expiry, revocation, and emergency stop | BLOCKED | The owner can manually suspend or uninstall the one App installation, but adapter-side preflight checks and a documented suspend/revoke rehearsal do not yet exist. |

No row marked **BLOCKED** may be treated as an activation approval. The next
safe increment—the source-only adapter contract, target-pinning validator, and
negative-test suite—was merged in PRs #650 and #651. They remain inert: neither
may read the private key, obtain a token, or contact GitHub. The remaining
blocked controls require a separately approved credential-handling and live-pilot
design.

## Recommended first bounded adapter

Use one GitHub App installation, restricted to one dedicated sandbox repository,
with a single permitted operation: **create one clearly labelled issue**. The
adapter must not merge, push a branch, create a release, change repository
settings, access organization administration, read or write secrets, trigger a
workflow, deploy, comment, close or reopen issues, or act outside the named
sandbox repository.

The App should have only repository metadata read and issues write permission.
Its private key or installation credential must remain outside Mission Control
records, logs, browser storage, and source control.

## Required evidence before activation

1. The owner names the exact dedicated sandbox repository and confirms that it
   contains no production data, integrations, or deployment secrets.
2. The owner confirms the exact initial operation: labelled issue creation, not
   a draft artifact or any other GitHub operation.
3. The CEO names the secondary emergency-stop operator required by the approved
   operating defaults.
   The operator's GitHub username is required to grant the corresponding
   organization-owner access.
4. A dedicated adapter security review proves target pinning, GitHub App
   permission minimization, no token logging, one-action leases, idempotency,
   expiry/revocation checks, and fail-closed behavior.
5. A recovery rehearsal is approved and recorded. It must use a separately
   planned sandbox-only follow-up action; no automatic rollback or deletion is
   permitted.
6. A bounded live-pilot policy specifies the maximum issue count, time window,
   labels, allowed title/body data class, approval packet shape, and audit
   evidence. The existing external-action budget remains US$0 until that pilot
   is explicitly activated.

## Activation boundary

Completing this checklist does not authorize implementation or activation. A
future request must explicitly approve the adapter design, the named repository,
the scoped GitHub App identity, the recovery rehearsal, and the bounded live
pilot. Each live issue creation remains an R3 external action requiring the
approved per-action CEO confirmation and preflight.

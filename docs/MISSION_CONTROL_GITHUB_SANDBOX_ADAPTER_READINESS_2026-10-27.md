# Mission Control GitHub sandbox adapter readiness

**Recorded:** 2026-10-27 JST  
**Status:** Design-only readiness assessment; no adapter, credential, workflow,
route, or execution authority is enabled.

## Current finding

The approval-gated foundation and the identity-only Google probe remain
non-authorizing. Repository review found no GitHub sandbox-adapter implementation,
no GitHub credential or token-provisioning path, no target-repository binding, and
no adapter activation workflow. This is the correct posture until the required
dedicated review and owner decision occur.

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
  required independent installation-stop authority. Before App registration,
  create a dedicated GitHub organization with the CEO and Ruby Bombeo as
  owners, transfer this empty sandbox repository to that organization, and
  register the App as organization-owned. No App, credential, installation, or
  issue has been created.

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

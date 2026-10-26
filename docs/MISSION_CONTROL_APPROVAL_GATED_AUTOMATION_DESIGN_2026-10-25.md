# Mission Control approval-gated automation design

**Recorded:** 2026-10-25 JST
**Status:** Design approved by owner; implementation and automation activation are not authorized by this record.
**Authority effect:** none

## Decision

Mission Control will use a human-authorized operating model. No model, task,
channel, notification, plan, prior approval, or worker availability state can
create execution authority. Every state-changing action requires a current,
durable CEO approval that is bound to the exact immutable plan revision, target,
scope, policy version, budget, and expiry. Material changes invalidate it.

The existing A0/read-only preview, gateway, proposal store, simulation-only
contracts, and audit read-model remain safety foundations. They must be extended
through new versioned contracts and bounded services, not weakened or treated as
implicit execution authority.

## Target architecture

1. **Mission intake** creates a correlated draft from a CEO conversation,
   approved project signal, or approved connected channel. It cannot execute.
2. **Planner** produces a structured, non-executable plan and impact preview.
   It cannot call external systems.
3. **Policy engine** assigns risk, resolves the required gates, verifies worker
   and action eligibility, and fails closed on unknown or incomplete evidence.
4. **Approval service** creates an immutable CEO approval packet and records an
   attributable decision. A UI state change alone is never approval.
5. **Execution coordinator** revalidates approval, policy, target, budget, and
   worker posture; only then it issues a one-time, short-lived execution lease.
6. **Action adapters** use their own least-privilege identity to perform exactly
   one allowlisted action after validating the lease. They cannot broaden scope,
   reuse authority, or chain arbitrary calls.
7. **Audit ledger and read model** retain correlated, privacy-bounded evidence
   and expose it to authorized operators without relying on application logs.

The public CEO gateway remains an authentication and bounded read boundary. A
separate internal automation service owns planning, approvals, leases, and
dispatch. Browser-facing routes must not become generic execution routes.

## Lifecycle and gates

```text
draft -> classified -> planning -> awaiting_approval
  -> approved_pending_preflight -> executing -> verifying
  -> completed | failed | stopped_for_review | expired | revoked
```

- Planning is non-authorizing.
- Every plan revision receives an immutable `plan_digest`.
- Approval binds to one plan revision, one target, one policy version, and one
  execution attempt. Any replan, retry, changed target, or changed scope requires
  a new approval.
- Preflight repeats immediately before dispatch: approval validity, revocation,
  expiry, plan digest, target state, adapter identity/health, worker eligibility,
  budget reservation, and policy version.
- A lease is single-use and constrained to one action. Multi-step batches require
  explicit display and approval of the ordered actions; default is per-step
  approval.
- Failure, unknown outcome, drift, expiry, policy mismatch, or retry request
  transitions to `stopped_for_review`. There are no automatic retries, reroutes,
  rollbacks, or compensations.
- A rollback is a distinct planned action and requires distinct approval unless it
  is proven non-mutating cleanup.

## Risk policy

Risk is separate from authority: authority defines which role/adapter may perform
an action; risk defines the human approval and evidence burden. The highest
applicable factor wins: environment, reversibility, financial/customer impact,
data sensitivity, breadth, privilege, external visibility, and uncertainty.
Unknown classifications are R4 by default.

| Level | Meaning | Default handling |
| --- | --- | --- |
| R0 | Read-only observation | No execution; preserve an audit record. |
| R1 | Reversible internal action | CEO approval before dispatch. |
| R2 | Operational mutation | CEO approval, explicit target/change preview, rollback plan, and preflight. |
| R3 | External, customer, financial, or production action | Per-action CEO approval, independent preflight and verification. |
| R4 | Credential, access, deletion, compliance, bulk, or high-impact action | Blocked until separately activated by dedicated policy and adapter review. |

## Owner-approved initial operating defaults

| Control | Approved initial default |
| --- | --- |
| R1 approval expiry | 24 hours |
| R2 approval expiry | 4 hours |
| R3 approval expiry | 15 minutes, one execution attempt |
| R4 | No approval route; remains blocked |
| R2 confirmation | Recent CEO reauthentication and explicit confirmation displaying target, environment, and plan digest |
| R3 confirmation | Recent CEO reauthentication, typed action/environment confirmation, and final preflight immediately before dispatch |
| External action budget | US$0 until a bounded live pilot is separately activated |
| Plan-only provider pilot | Shared atomic hard cap of US$5 per UTC day and US$1 per mission; explicit request/token limits and price schedule are required before dispatch |
| First permitted real adapter | Create a clearly labelled issue or draft artifact in one dedicated GitHub sandbox repository only; no merges, branch pushes, deployments, secrets, or production repositories |
| Raw conversation/task retention | 30 days |
| Approval/execution metadata and audit hashes | 1 year |
| Secrets | Never stored in Mission Control records, logs, or browser persistence |
| Emergency stop | CEO is primary and one named technical operator is secondary; either can stop new dispatches immediately. Restart requires CEO approval and a recorded safety review. |

A notification delivery receipt is not approval; the canonical decision remains
the durable CEO decision in Mission Control.

## Canonical identity and persistence decision

**Approved by owner: 2026-10-25 JST.**

- **Identity:** Google OIDC through an Authorization Code flow with PKCE S256,
  behind a server-side session service. CEO authority binds to the exact issuer
  and subject, never an email address alone. Browser sessions use opaque,
  Secure, HttpOnly, SameSite=Lax cookies with a 30-minute idle and 8-hour
  absolute limit; no browser token persistence. R2 requires an OIDC
  authentication no older than 15 minutes, and R3 no older than 5 minutes plus
  typed confirmation.
- **Break-glass:** a host-mounted, separately managed bearer token is limited to
  read-only recovery diagnostics. It cannot log in as the CEO, approve,
  delegate, or execute.
- **Persistence:** a dedicated PostgreSQL Mission Control database on the
  isolated Mission Control network, with no public database ingress and one
  least-privilege application role. Raw conversation/task content retention is
  30 days; approval/execution metadata and audit hashes are retained for one
  year. Secrets are never stored. Backups are encrypted and must pass a restore
  rehearsal before activation.
- **Audit:** persist append-only chained audit hashes and periodically sealed
  checkpoints.

These are canonical design decisions only. They do not install PostgreSQL,
configure a Google OAuth client, bind a CEO subject, create a session, or
activate a route.

## CEO UX

Primary navigation: **Inbox**, **Missions**, **Approvals**, **Activity**,
**Workers**, **Policies**, and **Settings**. The UI must distinguish live,
stale, unavailable, and synthetic data everywhere.

The mission detail shows risk, environment, expiry, and a plain statement that
no action has yet dispatched. The approval packet shows objective, ordered
actions, targets, affected systems, plan changes, risk reasons, policy version,
data categories, evidence references, budget, recovery proposal, worker/model,
and expiry. It offers only **Approve this exact plan**, **Reject**, or **Request
revision**.

R2+ decisions require reauthentication; R3 requires typed confirmation. After
submission, the UI shows a receipt but changes state only after durable storage
confirms the decision. Exceptions show the last safe checkpoint, attempted
action, known/unknown outcome, evidence reference, and choices to revoke future
work or create/approve a revised plan.

## Access, audit, and multi-model policy

- Roles: CEO (approve/reject/revoke), Chief of Staff (plan/request approval),
  Operator (read/troubleshoot), Auditor (redacted read), Worker/model (scoped
  task envelope), and Adapter identity (one action class/target domain).
- Enforce separation of duties. A principal or model may not create, approve, and
  execute the same work. Any CEO single-person exception is explicit policy and
  fully audited.
- The append-only audit ledger records actor, model/provider version, policy
  version, plan digest, approval scope, input/output digests, target references,
  idempotency key, event outcome, redacted evidence links, and chained hashes.
- Models are registered workers, not shared-credential principals. Registration
  declares task classes, risk ceiling, permitted capabilities, data class, budget,
  retention/residency posture, freshness, and kill-switch state. A model may not
  self-approve, inherit another worker's credentials, or call a broader-context
  worker without policy approval.

## Implementation sequence

1. Add versioned mission, plan, risk, approval-packet, decision, lease, attempt,
   exception, policy-decision, worker-registry, action-capability, and audit-v2
   contracts; no execution endpoint.
2. Build CEO conversation, plan drafting, approval inbox/packet,
   expiry/revocation, and correlated audit timeline.
3. Prove the complete flow against synthetic adapters, including negative tests
   for stale policy, expired/revoked approval, changed plan, duplicate dispatch,
   unavailable budget ledger, and ambiguous outcome.
4. Activate the GitHub sandbox adapter only after a dedicated security review,
   recovery rehearsal, identity-scope validation, and owner decision.
5. Add R2/R3 capabilities one action adapter at a time under separate activation
   records. Add other models first as plan-only workers.

The design-only [GitHub sandbox adapter readiness checklist](MISSION_CONTROL_GITHUB_SANDBOX_ADAPTER_READINESS_2026-10-27.md)
records the present non-authorizing posture and the evidence required before the
first real adapter can be proposed.

## Progress monitoring criteria

The recurring design review should inspect repository changes and report only:

1. completed or materially advanced implementation milestones;
2. drift from this approved boundary or any new route that could grant authority;
3. missing tests/evidence for the next gate;
4. a CEO decision required to progress; or
5. an explicit recommendation to pause/retire the monitor once the approved
   design is superseded or fully accepted.

The monitor must remain read-only: it must not edit files, create approvals,
dispatch actions, activate integrations, or change runtime configuration.

## Implementation progress

### Completed locally — 2026-10-25

- Added an inactive approval-gated contract pack for missions, risk assessments,
  plans, approval packets, disabled action capabilities, plan-only workers,
  non-issuable execution-lease previews, and chained audit events.
- Added a pure policy evaluator that applies the approved R0–R4 defaults:
  R1 is 24 hours, R2 is 4 hours with reauthentication, R3 is 15 minutes with
  typed confirmation, and R4 is blocked. It has no I/O, credential, provider,
  queue, adapter, or execution dependency.
- Added a local SQLite candidate store for inert missions, immutable plan
  digests, non-authorizing approval packets, and content-free chained audit
  hashes. It cannot issue a lease, enable an adapter, authorize execution, or
  mutate an external system.
- Added an unapplied PostgreSQL foundation migration plus a static validator.
  Its tables enforce `execution_authorized = false`,
  `mutation_authorized = false`, and `authority_effect = none`; the migration
  contains no grants, credentials, action adapter, or live database target.
- Added a visibly labelled synthetic Mission Control panel for an approval-gated
  mission. The browser validates the plan digest, risk, awaiting-decision state,
  and non-issued lease before rendering; invalid or authority-expanding fixture
  data fails closed. The panel has no controls or client write path.
- Focused verification passed: 26 Python tests across the contract, policy,
  store, session-policy, migration-validator, and probe-build-manifest suites;
  the Mission Control preview validator; JavaScript syntax check; posture UI
  test; Python compilation of the new modules; JSON parsing of the new schemas;
  and `git diff --check`.
- The existing inactive Google identity-probe source also compiles and its full
  13-test offline security suite passes in an isolated test environment. The
  test dependencies were certificate-validated against the locally trusted AVG
  inspection root; no TLS or certificate verification safeguard was bypassed.
  The disposable test environment and exported temporary certificate material
  were removed after verification.
- Corrected the inactive probe image and CI manifests to use published,
  test-verified dependencies: `cryptography==47.0.0`,
  `google-auth==2.50.0`, and `requests==2.32.4`. The prior pins for
  `google-auth==2.62.0` and `requests==2.34.2` were not published versions.
- Built `mission-control-google-identity-probe:local-verify` successfully on
  2026-10-25. Image inspection confirms its non-root `app` user and inactive
  entrypoint, with no activation environment variable; no container was run.
- Ran the local image once using no network, no mounts, no secrets, a read-only
  filesystem, and a disposable temporary directory. It exited fail-closed with
  `google_identity_probe_inactive`; the container removed itself.
- Strengthened the separately gated activation script: it now requires an exact
  explicit operator acknowledgement in addition to its immutable image digest,
  narrowly named secret volume, and canonical-host checks. Static tests protect
  its rollback, preflight isolation, secret-file permission, and route-scope
  invariants. Both Linux CI workflows also parse the script with `bash -n`.
- Applied the unapplied PostgreSQL migration only to a no-network, no-port,
  disposable local PostgreSQL 16 container. All four foundation tables and their
  constraints were created. A test insert with `execution_authorized = true`
  was rejected and stored no row; the temporary database container was removed.
- Ran the full 13-test identity-probe suite inside the built image itself, with
  no network, secrets, or writable application filesystem. All tests passed;
  the disposable test container removed itself.
- Workstation verification note: the current-user trusted-root store was
  refreshed from the official Windows Update root bundle before the test-only
  dependency download. The AVG inspection root was already trusted; its
  temporary exported PEM and the disposable test environment were removed
  after use. No production runtime, route, secret, or Mission Control authority
  setting was changed.

### Integration hold

The prior integration hold was released by owner approval on 2026-10-25. The
synthetic UI integration now layers on top of the existing Mission Control work
without altering its read-only connection, gateway routes, or authority state.
The next gateway/API increment remains contingent on activation prerequisites:
the owner-controlled Google client secret and CEO subject binding, deployment of
the isolated PostgreSQL/session-service environment, and separate activation
evidence. Until then, the gateway stays read-only and the approval-gated store
remains local-only.

### External provisioning status — 2026-10-25

- An authorized Hostinger VPS exists and is running, but its Docker Manager has
  no managed application listed.
- A strict, passwordless, read-only SSH check reached the VPS but no local key
  was authorized. No remote command was executed and no server setting changed.
- A dedicated passphrase-protected Ed25519 deployment key was created locally
  and its public half was added through Hostinger. Its public fingerprint is
  `SHA256:npjrQt/soqxOboW/aJvP0VsGKYuMaS+5cC9cj0qFSiE`. The private key and
  passphrase were not read or transmitted. Windows' optional SSH-agent service
  remains disabled because enabling it requires a separate administrator action.
- The pre-existing GitHub Actions deployment key and non-secret-named VPS
  configuration were then validated in the repository's diagnostic workflow
  run 40192916588: the secret presence checks, private-key format, host
  reachability, and passwordless SSH authentication all passed. The diagnostic
  made no VPS change.
- A clean, focused source-control review branch was created from the published
  Mission Control safety branch: `codex/approval-gated-automation-review`.
  Pull request [#615](https://github.com/phireij/phil-ai-os-platform/pull/615)
  records the inactive contracts, policy/store/session guards, identity probe,
  database migration, image definitions, CI, and this design record. It does
  not include the separately modified synthetic UI files.
- Pull request #615 passed all five required GitHub checks on 2026-10-25:
  `integrated-contract-regression`, `isolated-runtime-smoke`,
  `operations-foundation`, `verify-probe`, and
  `workflow-supply-chain-policy`.
- A reviewed immutable image publication and deployment entrypoint are still
  required before an isolated database, secret volume, or route can be created.
  Pull-request review and merge are source-control decisions only; they do not
  activate an action adapter, route, identity session, or execution authority.

### Gated identity-probe runtime preparation — 2026-10-25

- Pull request #615 was merged into `codex/mission-control-ui-safety` as
  `e03ea546544ee21d13c69dd41dad8088b1ba5dde`. Its review branch remains
  preserved for auditability.
- The next proposed increment is a manual-only GitHub Actions workflow with
  `preflight` and `activate` modes. `preflight` authenticates only long enough
  to inspect the VPS and pull an immutable image; it creates no route, secret
  volume, or container. `activate` requires the exact acknowledgement
  `approve-google-identity-probe-route` and is serialized against concurrent
  runs.
- The proposed activation path stages the Google client secret only through
  standard input into a new per-run Docker volume, validates `10002:10002` and
  mode `0400`, uses a read-only/capability-dropped container, verifies the
  public health endpoint, and restores the prior runtime if that verification
  fails. The route remains limited to `/auth/google` and the service reports
  `authority_effect=none`; it cannot create a Mission Control session or take
  an action.
- This workflow is source-controlled preparation only. It has not been
  dispatched, no container or route has been created, and no Google client
  secret has been copied to the VPS.

### Live-route audit and emergency containment — 2026-10-25

- A manual `preflight` run (GitHub Actions run `40194231852`) published and
  verified immutable image
  `sha256:6325fc1ba1cc0c317ebf7f2b1ffe302de6dfc35403fe2d544be930c63d8ddb96`,
  then stopped before VPS mutation because an existing `/auth/google` Traefik
  route was detected. It did not create a route, container, or secret volume.
- An owner-authorized read-only audit (run `40194835348`) found that
  `phil-ai-os-mission-control-google-ceo-session` was running with
  `conversation_authority=enabled` and exposed `/auth/google` together with
  conversation, notification, and task-proposal API prefixes. The audit read
  only metadata: image/restart state, route labels, mount names/destinations,
  and environment variable names; it did not read secret values.
- On owner authorization, emergency containment (run `40194953576`) set that
  container's restart policy to `no` and stopped it. Public verification
  confirmed that its `session_ready;conversation_authority=enabled` response
  was no longer available. No volume, secret, image, or rollback container was
  deleted.
- The audit identified stopped rollback containers, including an older Google
  identity-probe rollback. They do not serve traffic but remain preserved for
  recovery and prevent a replacement activation until a separately reviewed
  cleanup decision. The new workflow's audit and emergency-stop modes require
  distinct exact acknowledgements and now skip image publication/preflight.
- A proposed `cleanup` mode is restricted to exactly three audited stopped
  rollback containers. It checks that each remains stopped and has the expected
  immutable Mission Control image before removal; it preserves all volumes,
  images, and the currently contained CEO-session container. It is manual-only
  and requires the separate exact acknowledgement
  `approve-cleanup-stopped-mission-control-rollbacks`.

### Isolated identity-probe activation evidence — 2026-10-26

- The owner-authorized cleanup completed for the three explicitly audited
  stopped rollback containers. Volumes, images, and the contained legacy
  CEO-session container were preserved.
- The identity probe now uses a root-owned host file at
  `/opt/phil-ai-os-platform/mission-control/secrets/google-identity-probe-client-secret`,
  verified as `root:10002` mode `0640`, and bind-mounts it read-only at
  `/run/secrets/client_secret`. The secret value is supplied to the temporary
  stager only on standard input and is never emitted in workflow logs.
- Safety changes in pull requests [#626](https://github.com/phireij/phil-ai-os-platform/pull/626),
  [#627](https://github.com/phireij/phil-ai-os-platform/pull/627),
  [#628](https://github.com/phireij/phil-ai-os-platform/pull/628),
  [#629](https://github.com/phireij/phil-ai-os-platform/pull/629),
  [#630](https://github.com/phireij/phil-ai-os-platform/pull/630), and
  [#631](https://github.com/phireij/phil-ai-os-platform/pull/631) added bounded
  diagnostics, read-only temporary-container audit evidence, verified recovery
  for an isolated failed preflight, bounded local readiness polling, and
  cleanup on every failed exit. Each was merged only after its required CI
  passed.
- The separately acknowledged activation run `40328747122` completed
  successfully. It removed only a verified temporary preflight container,
  passed the fresh no-network local health preflight, and then verified the
  public endpoint `GET /auth/google/healthz` returns exactly
  `probe_ready;authority_effect=none`; `POST` to that endpoint returns `405`.
  The route is limited to `/auth/google` and does not create a Mission Control
  session, permit an action, or reactivate the CEO-session service.
- The legacy CEO-session containers remain stopped. A read-only audit also
  observed a stopped legacy CEO-session rollback container with retained route
  labels; it was not started, changed, or removed because it was outside the
  specifically approved containment and cleanup targets. Public probe health
  was `404` before the successful identity-probe activation.
- A post-deployment read-only audit (run `40329287851`) confirmed the identity
  probe is the only running container claiming `/auth/google`; both temporary
  probe container names are absent and public health is `200`. The contained
  CEO-session container remains stopped with restart policy `no`; the separate
  legacy CEO rollback remains stopped and untouched.

### Supervised Google identity-only exercise — 2026-10-26

- The owner completed a live Google sign-in through the isolated probe. The
  callback reported that Google identity verification succeeded and explicitly
  stated that no Mission Control session was created.
- No user identifier, OAuth authorization code, or token value is retained in
  this record. The temporary browser tab was closed after verification.
- This exercise confirms the identity-only boundary in the live path. It does
  not enable conversation, session, action-adapter, notification, task, or any
  other Mission Control runtime authority.

### Post-exercise read-only runtime audit — 2026-10-26

- The owner-authorized audit run `40334704300` completed successfully after
  the supervised exercise. It confirmed that the identity probe is the only
  running container claiming `/auth/google`, its public health status is
  `200`, and both named temporary probe containers are absent.
- The legacy CEO-session container remains stopped with restart policy `no`.
  Its separate legacy rollback container remains stopped and untouched; it was
  only reported as audit metadata. The audit made no VPS change.

### Privacy-redaction deployment preflight — 2026-10-26

- Pull request [#639](https://github.com/phireij/phil-ai-os-platform/pull/639)
  removed Google identity details from the probe callback response and added a
  regression test. It passed the full isolated probe CI and was merged without
  changing the live runtime.
- Preflight run `40337653664` published and verified immutable probe image
  `sha256:360c7c375cfb46cf14b40eae733c2acfc386b4d6ff86f1554e0668cecf0a8805`.
  It reported no route collision and completed with `authority_effect=none`;
  it created no route, secret, or container.
- Activating that image remains separately gated by the workflow's exact
  `approve-google-identity-probe-route` acknowledgement.

### Privacy-redaction activation and audit — 2026-10-26

- With the owner's fresh exact acknowledgement, activation run `40338617938`
  completed successfully. It passed the isolated readiness checks, public
  no-session/no-action verification, rollback finalization, and temporary
  registry-credential cleanup. The live callback now omits Google identity
  details while retaining the identity-only, no-session result.
- Post-deployment read-only audit run `40338994273` confirmed the probe is
  running image
  `sha256:3f98861b83e6fa93a4d30d8f9fe840d71e1560eba283c26fdb9ae321969beb08`,
  its public health is `200`, and its named preflight and rollback containers
  are absent. The legacy CEO-session container remains stopped with restart
  policy `no`; its stopped rollback container remains untouched.

### OIDC scope-minimization guard — 2026-10-27

- Pull request [#642](https://github.com/phireij/phil-ai-os-platform/pull/642)
  passed the isolated probe CI and locks the probe's authorization request to
  the provider-required minimum `openid email`. The probe discards identity
  claims after subject validation and does not display or retain them.
- The guard prevents unreviewed scope expansion. It is comments and regression
  coverage only, so it required no image publication or live redeployment.

# Mission Control posture v2 review packet

**Base:** public `main` at `6615cc137e0680496baebf964085fd8dc90bfefb` on 14 October 2026 (JST).
**Scope:** isolated posture bridge, read-only UI consumer, v2 contracts, and checks.
**Authority:** no new assignment, execution, approval, or provider calls.
**Release state:** review candidate only; no production merge or deployment.

## Problem and result

The shipped posture route still has the legacy v1 response shape. The read-only UI
expects the bounded v2 bridge. This change prepares a paired v2 producer and
consumer. It rejects upstream `grants_authority=true` claims, exposes only
allowlisted posture fields and handoff presence markers, and prevents a
source-reported `ready` state from being presented as current readiness before
an approved freshness policy exists. The host-local upstream refuses redirects
and bypasses proxy configuration.

The existing `ceo` password setup is not modified. The v2 bridge continues to
require the separate CEO bearer token already used by the authenticated gateway.
No secret is read by the local checks or stored in this branch.

## Changed components

| Component | Change | Production effect after merge |
|---|---|---|
| `ops/mission-control-public/read-model-bridge.py` | v2 allowlist, bounded upstream read, authority-claim rejection, pinned proxy-free local read | Gateway route changes only after a separately approved bridge deployment |
| `contracts/mission-control/agent-posture-bridge-*.json` | v2 inactive API description and response schema; `grants_authority` fixed false | None by itself |
| `apps/operations-hub/mission-control/mission-control.mjs` | Requires v2 and labels readiness as source reported with current freshness unknown | Static UI workflow automatically deploys on relevant `main` pushes |
| `scripts/test_mission_control_agent_posture_bridge.py` | Synthetic authorization, projection, privacy, limits, fail-closed, and transport checks | None |
| `apps/operations-hub/tests/test_mission_control_posture_ui.mjs` | Actual UI readiness-label behavior checks | None |
| Workflow files | Read-only PR contract CI; bridge image build runs the bridge checks | Bridge image publication on `main`; deployment remains manual |

## Local checks

- Seven synthetic bridge behavior checks: pass.
- UI readiness-label check: pass.
- Existing read-only preview validator: pass.
- Changed workflow supply-chain policy: pass.
- `git diff --check`: pass.

These checks do not prove live CEO authentication, exact deployed digest,
current upstream data, host isolation, or Hermes state. Full runtime JSON Schema
validation is still pending because the managed local Python runtime does not
include `jsonschema`; the code and targeted behavior checks remain the review
evidence for this candidate.

## Required release sequence

1. Review the scoped diff and the read-only PR checks on this exact revision.
2. Obtain the explicit production release approval required by the Mission
   Control operational acceptance gate. Note that merging the UI file into
   `main` triggers automatic static UI deployment; bridge image publication
   alone does not activate the v2 route.
3. Record the bridge image digest. Deploy the isolated bridge through the
   existing gated workflow and verify the expected v2 route with a preexisting
   authorized CEO token from a secure runtime, without copying it into chat or
   the repository. Verify container identity, route priority, and unchanged
   existing workloads.
4. Confirm the served UI module revision and v2 consumer behavior. If bridge
   activation fails, leave the read-only UI in its fail-closed unsupported
   contract state and use the reviewed isolated bridge rollback procedure.

The user-created `ceo` password is an existing access credential. Its exact
route and principal binding remain to be verified before durable CEO
conversation identity can be accepted. This package does not change that
identity boundary.

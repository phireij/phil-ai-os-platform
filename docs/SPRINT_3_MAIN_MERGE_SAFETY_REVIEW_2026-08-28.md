# Sprint 3 — Main Merge Safety Review

Date: 2026-08-28
Scope: PR #5 — bounded WooCommerce Foundation
Decision: MERGE-SAFE FOR REPOSITORY INTEGRATION / NO PRODUCTION ACTIVATION AUTHORITY

## Question

Could merging PR #5 to `main` unintentionally trigger an existing GitHub Actions workflow that deploys to the production VPS or otherwise expands production authority?

## Evidence reviewed

### 1. Recent ordinary `main` commits

Recent `main` documentation/control commits, including the Sprint 2 closure / Sprint 3 entry state, produced zero GitHub Actions runs. This rules out an unconditional broad `push`-to-`main` workflow at the current baseline.

### 2. Production-capable workflow trigger inspection

Representative current production-capable workflows were inspected directly from `main`:

- Phase 2.3 P5 Approved Activation
  - push trigger is limited to `ops/authorizations/phase-2-3-p5.txt`
  - also supports manual `workflow_dispatch`
  - requires the exact CEO authorization marker

- Phase 2.3 P4 Production Preflight
  - push trigger is limited to its exact preflight script and workflow file

- Phase 2.2 A5 Approved Activation
  - `main` push trigger is limited to the exact A5 CEO approval receipt document

- Phase 2.2 A6.4 Approved Specialist Presence Activation
  - `main` push trigger is limited to that exact historical activation workflow file

- Phase 2.1F Controlled Production Activation V4
  - `main` push trigger is limited to `.github/phase-2-1f-production-activation-v4-trigger`
  - also supports manual dispatch

- VPS Connection Test
  - push trigger is limited to the historical `docs/phase-1.16-progress-update` branch and `.github/vps-connection-trigger`
  - also supports manual dispatch

None of these trigger paths overlap PR #5's Sprint 3 commerce/contracts/docs files.

### 3. Workflow-file addition behavior on `main`

Commit `dba29d57289a4231465fd6aa12fabcfc6043d952` added the Phase 2.3 P5 approved activation workflow file to `main`. GitHub recorded zero Actions runs for that commit. This is strong direct evidence that adding an arbitrary workflow file does not match a hidden generic `.github/workflows/**` production trigger.

A later commit, `1d4f6d0994695212d9d9abc2e008a99b0d9ef47d`, added the standalone P5 independent-verification workflow. Exactly one Actions run occurred: that newly added workflow itself, because its own trigger explicitly includes its exact workflow path. No unrelated production workflow fired.

### 4. Sprint 3 workflow behavior

The Sprint 3 WooCommerce Foundation CI workflow itself:

- on pull request: watches only Sprint 3 commerce/CX/Operations paths and itself;
- on push: runs only on branches matching `sprint3/**`;
- grants `contents: read` only;
- contains no VPS SSH secrets or production WooCommerce credentials;
- runs isolated contract/unit/Compose checks and a local WordPress/WooCommerce smoke stack.

After merge to `main`, this Sprint 3 workflow does not have a `main` push trigger.

## PR #5 changed-path comparison

PR #5 changes are confined to bounded Sprint 3 areas such as:

- `.github/workflows/sprint-3-woocommerce-foundation-ci.yml`
- `commerce/woocommerce/**`
- `contracts/cx/**`
- `contracts/operations/**`
- Sprint 3 / Ruby commerce planning documentation

No historical production activation authorization marker or production activation trigger path is changed by the PR.

## Decision

The previous merge uncertainty is materially resolved.

**PR #5 is safe to merge into `main` as repository integration work.**

This decision means only that the repository merge will not intentionally or implicitly authorize production WooCommerce access or a production VPS activation workflow.

It does **not** authorize:

- production WooCommerce identity or credentials;
- live WooCommerce connectivity;
- live catalog/inventory/media/order mutations;
- payment or DNS/site activation;
- specialist enablement;
- new execution task classes;
- higher autonomy;
- automatic production actions;
- Mission Control mutation authority.

Those remain behind their explicit CEO gate.

`PHIL_AI_OS_SPRINT_3_MAIN_MERGE_SAFETY_GREEN`

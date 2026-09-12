# Sprint 7 — Main Branch Protection Readiness

Date: 2026-09-12  
Status: ENGINEERING READINESS GREEN / LIVE ADMIN GATE OPEN

## Purpose

Prepare the repository-side evidence needed for the Master Executive Roadmap requirement that `main` branch protection/ruleset be active before public launch.

## Observed live GitHub state

A read-only inspection of the repository rulesets endpoint on 2026-09-12 returned an empty collection (`[]`). Therefore the launch requirement **must not be considered satisfied yet**.

This record does not grant repository administration authority and does not alter GitHub settings.

## Desired launch policy

The bounded policy in `governance/github/main-branch-protection-policy.json` requires a ruleset that targets `main` (or GitHub's default-branch selector), is actively enforced, and contains:

- pull-request protection
- branch deletion protection
- non-fast-forward / force-push protection
- required status checks
- required review-thread resolution
- the integrated contract regression and isolated runtime smoke checks as required status contexts

The policy currently permits zero mandatory approving reviews because the repository is operated by a single owner/CEO workflow; it still requires pull-request flow and review-thread resolution. This can be strengthened later without weakening the launch gate.

## Executable readiness evidence

- policy: `governance/github/main-branch-protection-policy.json`
- validator: `scripts/validate_main_branch_ruleset.py`
- CI: `.github/workflows/sprint7-main-branch-protection-readiness-ci.yml`

The validator fails closed when:

- no ruleset targets `main`
- enforcement is not active
- deletion, non-fast-forward, pull-request, or required-status-check rules are missing
- fewer than the required status checks are configured
- required Integrated Readiness contexts are missing
- pull-request review-thread resolution is not required

Self-test marker:

`PHIL_AI_OS_MAIN_BRANCH_RULESET_VALIDATOR_SELF_TEST_GREEN authority_effect=none`

## Remaining admin gate

A repository administrator must create/activate the actual GitHub ruleset. After that, export or read the repository rulesets API response and validate it with:

`python scripts/validate_main_branch_ruleset.py --rulesets <rulesets.json>`

Expected live-state marker only after compliant activation:

`PHIL_AI_OS_MAIN_BRANCH_RULESET_GREEN`

Until that marker can be produced from current GitHub evidence, branch protection remains a **NO-GO launch item**.

## Authority boundary

This readiness package does not:

- change GitHub repository settings
- grant admin rights
- activate production deployment
- change WooCommerce, payments, SMS, inventory, channel replies, Mission Control, Hermes or DNS authority

Production authority effect remains `none`.

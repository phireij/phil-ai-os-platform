# Mission Control project-state CI path coverage

**Base:** `main` at `f40fe3e2f0c275ab23f753c3356d5765f433e226` when this isolated branch was created.
**Scope:** trigger filters for the existing read-only Project State Observation CI.
**Authority:** no collector schedule, live source, mutation, or freshness-policy change.

The workflow on `main` watched observation files, one registry file, and itself.
The Mission Control UI change in PR #482 therefore did not trigger this workflow.
This change extends both push and pull-request filters to the project-state and
registry trees, Mission Control contracts/UI, and the specific freshness,
reconciliation, and collector scripts that can change the observation context.

The workflow still validates repository observation fixtures with its existing
read-only job. A successful run establishes that the checked-in fixtures pass
that job on the exact commit. It does not establish current project status,
source freshness, authenticated runtime behavior, or operational acceptance.

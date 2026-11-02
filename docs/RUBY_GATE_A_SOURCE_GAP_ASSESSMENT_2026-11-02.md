# Ruby Gate A Source Gap Assessment — 2 November 2026

## Scope and conclusion

This is a source-and-test reconciliation of the approved Gate A staging intent. It does not activate the fixture, configure a runtime, create an access/retention/security policy, deploy, access live data, or take a business action.

PR #794 is a useful first source step, but Gate A is **not complete**. It supplies a single fixture-only endpoint; it is not the owner review UI and does not provide a real Ruby review-record transport.

## What the current source proves

`ops/mission-control-identity/ruby_review_synthetic.py` creates one fixed, minimal synthetic pending-review record and one identifier-only synthetic audit event. It has no Core-store, filesystem, network, or customer-data dependency. The response disables exports and all authority flags.

`google_ceo_session.py` exposes that fixture only at the closed `GET /api/ruby-review-synthetic` shape. The route is absent unless the exact `MISSION_CONTROL_RUBY_REVIEW_SYNTHETIC_SURFACE_ENABLED=true` value is present, rejects a query string, and rejects a missing session. Existing request handling enforces its Host boundary before dispatch; this handler does **not** add an explicit Origin predicate.

The current flag is an exact feature-value guard only. It does **not** independently establish that the process is in a non-production environment. The current tests cover default `404`, authenticated-session requirement, closed query rejection, fixture-only data, export denial, and non-authority fields.

## Remaining Gate A source/test gaps

| Design element | Current state | Required before it can be called complete |
| --- | --- | --- |
| Owner review UI | Absent. No page or client renders the fixture, synthetic banner, record/audit view, or disabled controls. | Approve a closed, read-only fixture UI shape and its negative tests. |
| Review-record transport | Deliberately absent. The endpoint never reads `ConversationStore` Ruby records and accepts no input. | Separate route/security, owner/project policy, retention, audit, transport, and activation decisions; not in Gate A source scope. |
| Synthetic data presentation | One fixed record/audit pair only; no selection, pagination, filtering, export, edit, or approval action exists. | Decide the minimal fixture scenarios and fields a UI may show, while retaining no actions and no parameters. |
| Environment containment | The feature is disabled by default and exact-value enabled, but has no independent environment-tier verification. | A separately reviewed runtime/activation design, if an environment constraint is required. Do not infer it from the current helper. |
| Browser request boundary | Existing Host and session checks apply; no route-specific Origin check exists. | Decide whether the future UI/API design requires an explicit Origin predicate in addition to the existing same-origin cookie/Host model. |
| Owner identity semantics | A valid existing CEO session is required; no Ruby-specific owner role or project-policy configuration is introduced. | Separate access-policy decision before any real-record reader/transport. |

## Proposed next bounded step

If the owner wants to advance Gate A without crossing into real records or activation, approve a **read-only synthetic review UI design** with these fixed constraints:

1. It uses only the existing closed fixture endpoint and shows an always-visible synthetic/non-authorizing label.
2. It renders only an approved fixed field list for the one synthetic record and identifier-only audit event.
3. It offers no create, edit, approve, export, filter, project selection, pagination, or retry controls.
4. It remains disabled by default and has tests for disabled, unauthenticated, query-bearing, and no-action cases.

The two required design decisions are the approved display fields/fixture scenarios and whether the future route must add an explicit Origin predicate. Real Core transport remains a separate, currently unapproved gate.

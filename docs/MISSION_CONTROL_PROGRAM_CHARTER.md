# Mission Control program charter

**Status:** living completion contract
**Owner:** Phil
**Last reconfirmed:** 30 October 2026 JST

## Why this document exists

Mission Control work is recorded across implementation, security, delivery, and
release documents. This charter is the single reference for answering three
executive questions consistently:

1. What is Mission Control ultimately meant to do?
2. What must be true before it can be called complete?
3. What is the current status, timeline, and next blocker?

The delivery tracker remains the source for task-level evidence and current
observations. The executive roadmap remains the source for the broader platform
sequence. If either document conflicts with this charter about the intended
Mission Control outcome, flag the conflict and resolve it before reporting
completion.

## Intended end state

Mission Control is the governed operational control plane for Phil AI OS. Its
complete path is:

`CEO -> Mission Control -> CTO / approved agents -> bounded task routing and execution -> results -> CEO notification and approval`

At completion, the CEO can give the CTO or an approved agent a defined task
through Mission Control, see attributable progress and results, and receive
appropriate notifications and approval requests. Mission Control must support:

- authenticated CEO control and owner-scoped history;
- governed task proposal, decision, assignment, status, and result lifecycle;
- CTO/agent task dispatch and result return through an explicit, auditable
  contract;
- notifications, escalation, audit, backup, recovery, rollback, and health
  evidence; and
- a release decision based on one exact, reproducible integrated acceptance
  revision.

The read-only CTO context connector in MC-021 is an enabling component, not the
whole CTO workflow. Completing it alone does not satisfy the CTO/agent task
dispatch and results outcome above.

## Completion test

Do not call Mission Control complete, operational, or release-ready unless all
of the following have current evidence:

1. The authenticated CEO can create a governed task request and see its state.
2. The approved CTO/agent path can accept an allowed task, return a correlated
   result, and expose status without relying on an untracked manual handoff.
3. Any provider, connector, or external delivery used by that path has passed
   its protected-input, least-privilege, budget, retry, and failure-handling
   acceptance gates.
4. CEO notification, approval, audit, escalation, backup/restore, rollback,
   monitoring, and workload-isolation evidence pass together on one exact
   release candidate.
5. The applicable CEO/CTO release decision is recorded before any authority
   expansion or production action.

## Automation and authority boundaries

“Full automation” is the target workflow, not permission to bypass its safety
contracts. Normal allowed task routing can be automated once its explicit
contract and acceptance evidence are complete. New external mutations,
credential introduction, spending changes, new task classes, or scope changes
remain separately governed and fail closed until their applicable gates are
satisfied. This prevents an implementation work item from being mistaken for
authority to act outside its approved scope.

## Reporting protocol

Every future progress, timeline, or goal report must begin by consulting this
charter and the current delivery tracker. It must state:

1. the end-state above;
2. task-level completion versus operational readiness separately;
3. the exact revision/evidence date for any claimed current status;
4. the critical-path blockers and their required inputs; and
5. whether a capability is implemented, verified, activated, or merely
   proposed.

Never report a percentage alone. If a percentage is requested, pair the task
count with the completion test and clearly identify unfinished critical gates.

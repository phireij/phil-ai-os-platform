# AO-MVP Host-Independent Predeployment Acceptance

Status: ACCEPTED FOR PREDEPLOYMENT ENGINEERING — HOSTED ACTIVATION NOT AUTHORIZED

The repository-side persistent-orchestrator foundation is complete through the hosted activation gate.

Accepted contracts:
- durable queue selection and dependency checks;
- A1 allowlist/denylist enforcement;
- durable replay protection;
- lifecycle state machine and immutable terminal states;
- independent verification and approval escalation;
- scheduler cadence and clock-regression handling;
- single-worker lease, heartbeat, expiry recovery;
- bounded service-loop composition;
- runtime health/readiness and log redaction;
- persisted-state corruption detection;
- synthetic stop/A0 rollback;
- inert runtime package manifest;
- fail-closed hosted readiness record;
- exact activation evidence template and validator.

Current state remains NOT READY for hosted activation because host-specific evidence does not yet exist: approved target/runtime, persistent-volume restart proof, immutable deployed package/image digest, exact deployed-revision CI linkage, and explicit hosted-runtime activation authorization.

No production/provider mutation authority is granted by this acceptance. PR #421 remains a development artifact and merge is separately gated.

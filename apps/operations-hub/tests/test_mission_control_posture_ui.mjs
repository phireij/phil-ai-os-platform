import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const source = readFileSync(new URL("../mission-control/mission-control.mjs", import.meta.url), "utf8");
const start = source.indexOf("function displayAgentReadiness(agent, sourceGeneratedAt) {");
const end = source.indexOf("\nasync function loadLiveAgentPosture", start);
assert.ok(start >= 0 && end > start, "posture display function must exist");
const displayAgentReadiness = runInNewContext(
  `${source.slice(start, end)}\ndisplayAgentReadiness`,
  { Date, Number },
);

const readyAgent = {
  evidence_complete: true,
  registry: { enabled: true, assignable: true, evidence_complete: true },
  presence: {
    state: "fresh", identity_verified: true, evidence_complete: true,
    observed_at: "2026-10-13T23:59:30Z", age_seconds: 30,
  },
  workload: { evidence_complete: true, active_task_count: 0 },
  readiness: { state: "ready", grants_authority: false },
};

const sourceTime = "2026-10-14T00:00:00Z";
assert.equal(displayAgentReadiness(readyAgent, sourceTime), "source-reported ready · current freshness unknown");
assert.equal(displayAgentReadiness(readyAgent, null), "indeterminate · evidence incomplete");
assert.equal(
  displayAgentReadiness({ ...readyAgent, presence: { ...readyAgent.presence, age_seconds: 121 } }, sourceTime),
  "indeterminate · evidence incomplete",
);
assert.equal(
  displayAgentReadiness({ ...readyAgent, readiness: { state: "ready", grants_authority: true } }, sourceTime),
  "indeterminate · evidence incomplete",
);
assert.equal(
  displayAgentReadiness({ ...readyAgent, readiness: { state: "busy", grants_authority: false } }, sourceTime),
  "busy · current freshness unknown",
);
console.log("Mission Control posture UI freshness labels: GREEN");

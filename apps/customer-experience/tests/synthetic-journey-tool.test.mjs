import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";

const toolUrl = new URL("../tools_synthetic_journey_smoke.mjs", import.meta.url);

test("synthetic customer journey smoke tool emits the bounded GREEN marker", () => {
  const output = execFileSync(process.execPath, [toolUrl.pathname], {
    encoding: "utf8",
    env: { ...process.env },
  });

  assert.match(output, /PHIL_AI_OS_SPRINT_4_END_TO_END_SYNTHETIC_GREEN/);
  assert.match(output, /locales=en,ja/);
  assert.match(output, /ready_path=true/);
  assert.match(output, /blocked_path=true/);
  assert.match(output, /network_call=false/);
  assert.match(output, /mutation=false/);
  assert.match(output, /order_creation=false/);
  assert.match(output, /payment_execution=false/);
  assert.match(output, /live_mode=false/);
});

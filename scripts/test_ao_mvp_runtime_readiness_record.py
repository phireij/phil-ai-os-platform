#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];r=json.loads((ROOT/"ops/runtime/ao-mvp-hosted-runtime-readiness.v1.json").read_text())
assert r["status"]=="predeployment_not_ready"
assert r["deployment_authorized"] is False and r["production_mutation_authorized"] is False
assert r["checks"]["persistent_volume"] is False
assert r["checks"]["exact_revision_ci"] is False
assert all(r["checks"][k] is True for k in ("single_worker_exclusion","corrupt_state_fail_closed","log_redaction","egress_policy","a1_denylist","rollback"))
print("AO-MVP hosted runtime readiness record: GREEN (predeployment not ready)")

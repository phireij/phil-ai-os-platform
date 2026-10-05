#!/usr/bin/env python3
"""Validate active A1 remains bounded to the CEO-approved engineering allowlist."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
m=json.loads((ROOT/"ops/authorizations/a1-authority-matrix.v1.json").read_text())
r=json.loads((ROOT/"ops/authorizations/a1-activation-record-2026-10-05.json").read_text())
q=json.loads((ROOT/"ops/autonomous-work-queue/work-queue.v1.json").read_text())
assert m["activation_state"]=="active"
assert m["effective_autonomy_ceiling"]=="A1"
assert all(m["activation_preconditions"].values())
assert m["automatic_execution_enabled"] is True
assert m["production_mutation_authorized"] is False
assert r["effective_autonomy_ceiling"]=="A1"
for k in ["production_mutation_authorized","live_customer_messaging_authorized","payment_execution_authorized","pull_request_merge_authorized","dns_change_authorized","kcfc_production_action_authorized"]:
 assert r[k] is False
assert r["rollback_target"]=="A0"
assert q["autonomy_ceiling"]=="A1"
assert q["execution_enabled"] is True
a1=next(i for i in q["items"] if i["work_id"]=="ao-work:a1-activation")
assert a1["selection"]["execution_authorized"] is False
print("AO-8 bounded A1 activation contract: GREEN")

#!/usr/bin/env python3
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; p=ROOT/"scripts/ao_mvp_approval_escalation.py"
s=importlib.util.spec_from_file_location("e",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
r=m.escalate({"work_id":"x","project_id":"phil-ai-os"},"outside_a1")
assert r["approval_granted"] is False and r["execution_authorized"] is False
assert r["authority_effect"]=="none" and r["production_mutation"] is False
print("AO-4 approval escalation contract: GREEN")

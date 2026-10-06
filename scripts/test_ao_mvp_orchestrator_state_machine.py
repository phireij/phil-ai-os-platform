#!/usr/bin/env python3
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; p=ROOT/"scripts/ao_mvp_orchestrator_state_machine.py"
s=importlib.util.spec_from_file_location("m",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
r=m.new("ao-work:test")
for nxt in ["selected","policy_allowed","dispatched_simulation","verification_pending","verified_success"]:
 r=m.transition(r,nxt,"fixture")
assert r["state"]=="verified_success" and r["execution_performed"] is False and r["production_mutation"] is False
try: m.transition(r,"selected","bad")
except ValueError: pass
else: raise AssertionError("terminal state mutated")
try: m.transition(m.new("x"),"verified_success","bad")
except ValueError: pass
else: raise AssertionError("invalid transition accepted")
print("AO-4 persistent orchestrator state-machine contract: GREEN")

#!/usr/bin/env python3
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; p=ROOT/"scripts/ao_mvp_verification_gate.py"
s=importlib.util.spec_from_file_location("v",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
good={"work_id":"x","execution_performed":False,"production_mutation":False,"adapter_status":"success","evidence_refs":["fixture"],"checks_green":True}
assert m.verify(good)["decision"]=="verified_success"
for bad in [
 {**good,"adapter_status":"unknown"},{**good,"evidence_refs":[]},{**good,"checks_green":False},{**good,"production_mutation":True}
]: assert m.verify(bad)["decision"]=="failed"
print("AO-4 independent verification gate: GREEN")

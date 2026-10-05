#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"scripts/ao_mvp_inert_selector.py"
s=importlib.util.spec_from_file_location("selector",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
r=m.select()
assert r["selected_work_id"]=="ao-work:ao1-evidence-adapters"
assert r["execution_authorized"] is False
assert r["mutation_authorized"] is False
assert r["authority_effect"]=="none"
assert r["candidate_count"]==1
print("AO-MVP inert selector: GREEN")

#!/usr/bin/env python3
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"scripts/ao_mvp_a1_selector.py"; s=importlib.util.spec_from_file_location("s",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
r=m.select()
assert r["selected_work_id"]=="ao-work:ao4-synthetic-orchestrator"
assert r["capability"]=="tests_static_analysis"
assert r["execution_authorized"] is False and r["mutation"] is False and r["production"] is False
print("AO-MVP active A1 selector: GREEN")

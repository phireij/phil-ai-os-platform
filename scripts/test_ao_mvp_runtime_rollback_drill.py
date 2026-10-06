#!/usr/bin/env python3
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/"scripts/ao_mvp_runtime_rollback_drill.py";s=importlib.util.spec_from_file_location("x",p);assert s and s.loader;m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
r=m.rollback({"revision":"fixture","effective_autonomy":"A1","service_state":"running"})
assert r["service_state"]=="stopped" and r["effective_autonomy"]=="A0"
assert r["dispatch_enabled"] is False and r["production_mutation_authorized"] is False
assert r["evidence_preserved"] is True and r["authority_effect"]=="reduce_only"
print("AO-MVP synthetic runtime rollback drill: GREEN")

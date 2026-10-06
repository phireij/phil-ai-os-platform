#!/usr/bin/env python3
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/"scripts/ao_mvp_runtime_health.py";s=importlib.util.spec_from_file_location("x",p);assert s and s.loader;m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
good={k:True for k in ("state_volume_readable","authority_matrix_loaded","lease_backend_ready","denylist_loaded")}
assert m.project(good)["status"]=="ready"
for k in good:
 b=dict(good);b[k]=False;assert m.project(b)["status"]=="not_ready"
assert m.project(good)["mutation_authorized"] is False
print("AO-MVP runtime health projection: GREEN")

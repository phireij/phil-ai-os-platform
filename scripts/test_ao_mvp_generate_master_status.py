#!/usr/bin/env python3
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; p=ROOT/"scripts/ao_mvp_generate_master_status.py"
s=importlib.util.spec_from_file_location("g",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m); d=m.build()
assert d["authority_effect"]=="none" and d["autonomy_ceiling"]=="A0"
assert d["overall_status"]=="yellow"
ids=[x["project_id"] for x in d["projects"]]
assert ids==["phil-ai-os","rubys-cake-delights-hq","kcfc-portal"]
phil=d["projects"][0]; ruby=d["projects"][1]; kcfc=d["projects"][2]
assert phil["status"]=="green"
assert ruby["status"]=="yellow" and any("stale" in x.lower() for x in ruby["blockers"])
assert kcfc["status"]=="yellow" and any("staging" in x.lower() for x in kcfc["blockers"])
assert all(x["authority"]["mutation_authorized"] is False for x in d["projects"])
print("AO master-status generation contract: GREEN")

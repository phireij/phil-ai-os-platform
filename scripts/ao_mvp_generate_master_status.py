#!/usr/bin/env python3
"""Regenerate committed AO master status from the deterministic reconciler."""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
target=ROOT/"scripts/reconcile_ao_project_state.py"
spec=importlib.util.spec_from_file_location("reconcile",target); assert spec and spec.loader
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def build():
 data=m.build()
 statuses=[p["status"] for p in data["projects"]]
 data["overall_status"]="red" if "red" in statuses else "unknown" if "unknown" in statuses else "yellow" if "yellow" in statuses else "green"
 data["generated_from"]="AO-1 explicit project observations"
 return data
if __name__=="__main__": print(json.dumps(build(),indent=2,sort_keys=True))

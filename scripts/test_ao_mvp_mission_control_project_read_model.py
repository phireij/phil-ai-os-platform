#!/usr/bin/env python3
"""Contract checks for the AO-MVP Mission Control read-only patch."""
from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
patch_path=ROOT/"scripts/ao_mvp_patch_mission_control_project_read_model.py"
base_path=ROOT/"scripts/phase2_2_a7_4_multi_agent_read_model.py"

spec=importlib.util.spec_from_file_location("ao_mc_patch",patch_path)
assert spec and spec.loader
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
source=base_path.read_text(encoding="utf-8")
patched=mod.patch(source)

assert "ao-mvp.master-projects.v1" in patched
assert "mutation_authorized':False" in patched
assert "authority_effect':'none" in patched
assert "data['master_projects'] = master_project_projection()" in patched
assert "subprocess.run" in patched  # existing read model retained, not replaced
try:
    mod.patch(patched)
except SystemExit:
    pass
else:
    raise AssertionError("patch must refuse duplicate application")
print("AO-MVP Mission Control read-model patch contract: GREEN")

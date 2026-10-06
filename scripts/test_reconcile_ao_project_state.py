#!/usr/bin/env python3
"""Self-contained AO-1 reconciler contract checks."""
from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "scripts/reconcile_ao_project_state.py"
spec = importlib.util.spec_from_file_location("ao_reconcile", target)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load reconciler")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

data = mod.build()
assert data["authority_effect"] == "none"
assert data["autonomy_ceiling"] == "A0"
projects = data["projects"]
assert [p["project_id"] for p in projects] == ["phil-ai-os", "rubys-cake-delights-hq", "kcfc-portal"]
for project in projects:
    assert project["authority"]["autonomy_ceiling"] == "A0"
    assert project["authority"]["mutation_authorized"] is False
    assert project["status"] in {"green", "yellow", "red", "unknown"}

ruby = next(p for p in projects if p["project_id"] == "rubys-cake-delights-hq")
assert "Quick Pickup production activation readiness is false" in ruby["blockers"]
kcfc = next(p for p in projects if p["project_id"] == "kcfc-portal")
assert kcfc["repository_state"]["ref"] == "redesign/mobile-first-v2"
print("AO-1 static reconciler contract: GREEN")

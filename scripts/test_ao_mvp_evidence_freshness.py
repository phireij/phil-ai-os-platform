#!/usr/bin/env python3
"""Fail-closed AO-1 evidence reconciliation tests."""
from __future__ import annotations
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"scripts/reconcile_ao_project_state.py"; s=importlib.util.spec_from_file_location("r",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
registry=m.load(m.REGISTRY); phil=next(x for x in registry["projects"] if x["project_id"]=="phil-ai-os")
base={"schema":"phil-ai-os-project-observation","version":1,"project_id":"phil-ai-os","source_kind":"github_ci","observed_at":"2026-10-05","authority":{"authority_effect":"none","mutation_authorized":False},"_ref":"fixture"}
fresh={**base,"freshness":"fresh","facts":{"contract_ci":"success","supply_chain":"success"}}
stale={**fresh,"freshness":"stale"}
assert m.reconcile(phil,[fresh])["status"]=="green"
assert m.reconcile(phil,[stale])["status"]=="unknown"
assert m.reconcile(phil,[])["status"]=="unknown"
print("AO-1 evidence freshness fail-closed tests: GREEN")

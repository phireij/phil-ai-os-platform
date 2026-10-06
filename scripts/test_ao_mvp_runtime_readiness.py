#!/usr/bin/env python3
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/"scripts/ao_mvp_runtime_readiness.py";s=importlib.util.spec_from_file_location("x",p);assert s and s.loader;m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
assert m.evaluate({})["ready"] is False
allgreen={k:True for k in m.REQUIRED};r=m.evaluate(allgreen)
assert r["ready"] is True and r["deployment_authorized"] is False
bad={**allgreen,"rollback":False};assert m.evaluate(bad)["ready"] is False and "rollback" in m.evaluate(bad)["missing"]
print("AO-MVP hosted runtime readiness evaluator: GREEN")

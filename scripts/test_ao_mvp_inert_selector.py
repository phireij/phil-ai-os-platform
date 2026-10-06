#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"scripts/ao_mvp_inert_selector.py"
s=importlib.util.spec_from_file_location("selector",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
matrix=json.loads((ROOT/"ops/authorizations/a1-authority-matrix.v1.json").read_text())
if matrix["effective_autonomy_ceiling"]=="A0":
    r=m.select()
    assert r["selected_work_id"]=="ao-work:ao1-evidence-adapters"
    assert r["execution_authorized"] is False
    assert r["mutation_authorized"] is False
    assert r["authority_effect"]=="none"
else:
    try:
        m.select()
    except SystemExit as exc:
        assert "requires A0" in str(exc)
    else:
        raise AssertionError("pre-activation inert selector must fail closed once A1 is active")
print("AO-MVP inert selector phase contract: GREEN")

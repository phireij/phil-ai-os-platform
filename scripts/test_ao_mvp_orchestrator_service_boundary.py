#!/usr/bin/env python3
import importlib.util,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; p=ROOT/"scripts/ao_mvp_orchestrator_service_boundary.py"
s=importlib.util.spec_from_file_location("x",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/"lease.json"
 assert m.acquire(p,"worker-a",100,30)["acquired"] is True
 assert m.acquire(p,"worker-b",110,30)["acquired"] is False
 assert m.acquire(p,"worker-b",131,30)["acquired"] is True
 assert m.release(p,"worker-a") is False
 assert m.release(p,"worker-b") is True
print("AO-4 restart-safe orchestrator lease boundary: GREEN")

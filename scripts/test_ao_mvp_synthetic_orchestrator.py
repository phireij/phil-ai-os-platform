#!/usr/bin/env python3
import importlib.util,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; p=ROOT/"scripts/ao_mvp_synthetic_orchestrator.py"
s=importlib.util.spec_from_file_location("o",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
with tempfile.TemporaryDirectory() as td:
 ledger=Path(td)/"ledger.jsonl"
 a=m.iterate(ledger)
 assert a["state"]=="planned" and a["execution_performed"] is False
 assert a["decision"]["decision"]=="allow_simulation"
 b=m.iterate(ledger)
 assert b["state"]=="replay_denied" and b["execution_performed"] is False
 assert len(ledger.read_text().splitlines())==1
print("AO-4 synthetic orchestrator iteration: GREEN")

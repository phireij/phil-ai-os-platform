#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path); assert s and s.loader
 m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
l=load("ledger","scripts/ao_mvp_durable_dispatch_ledger.py")
d=load("dispatcher","scripts/ao_mvp_a1_dispatcher_simulation.py")
import json
matrix=json.loads((ROOT/"ops/authorizations/a1-authority-matrix.v1.json").read_text())
req={"work_id":"ao-work:ao5-mission-control-projection","capability":"tests_static_analysis","production":False,"mutation":False}
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/"dispatch.jsonl"; store=l.DurableDispatchLedger(p)
 first=d.DispatchLedger().decide(req,matrix)
 assert first["decision"]=="allow_simulation" and first["execution_performed"] is False
 assert store.append_once(first) is True
 assert store.contains(first["dispatch_id"]) is True
 restarted=l.DurableDispatchLedger(p)
 assert restarted.append_once(first) is False
 rows=[json.loads(x) for x in p.read_text().splitlines()]
 assert len(rows)==1 and rows[0]["production_mutation"] is False
print("AO-MVP durable dispatch replay contract: GREEN")

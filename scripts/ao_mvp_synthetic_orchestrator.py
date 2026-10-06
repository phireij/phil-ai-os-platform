#!/usr/bin/env python3
"""AO-4 one-iteration synthetic orchestrator.

Selection -> policy decision -> durable decision record. It performs no selected
work itself and exposes no production/provider mutation primitive.
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def loadmod(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path); assert s and s.loader
 m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
sel=loadmod("sel","scripts/ao_mvp_a1_selector.py")
disp=loadmod("disp","scripts/ao_mvp_a1_dispatcher_simulation.py")
dur=loadmod("dur","scripts/ao_mvp_durable_dispatch_ledger.py")
MATRIX=ROOT/"ops/authorizations/a1-authority-matrix.v1.json"
def iterate(ledger_path:Path):
 plan=sel.select()
 if not plan.get("selected_work_id"):
  return {"state":"idle","plan":plan,"execution_performed":False}
 req={"work_id":plan["selected_work_id"],"capability":plan["capability"],"production":False,"mutation":False}
 matrix=json.loads(MATRIX.read_text())
 decision=disp.DispatchLedger().decide(req,matrix)
 store=dur.DurableDispatchLedger(ledger_path)
 if store.contains(decision["dispatch_id"]):
  return {"state":"replay_denied","plan":plan,"decision":{**decision,"decision":"deny","reason":"durable_replay"},"execution_performed":False}
 persisted=store.append_once(decision)
 return {"state":"planned" if decision["decision"]=="allow_simulation" else "denied","plan":plan,"decision":decision,"decision_persisted":persisted,"execution_performed":False}

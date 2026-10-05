#!/usr/bin/env python3
"""Bounded persistent local-loop composition.

Persists orchestrator lifecycle records and dispatch decisions locally. The
runner plans/verifies only; it has no provider or production mutation adapter.
"""
from __future__ import annotations
import importlib.util,json,os,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path); assert s and s.loader
 m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
selector=mod("selector","scripts/ao_mvp_a1_selector.py")
dispatcher=mod("dispatcher","scripts/ao_mvp_a1_dispatcher_simulation.py")
ledger=mod("ledger","scripts/ao_mvp_durable_dispatch_ledger.py")
sm=mod("sm","scripts/ao_mvp_orchestrator_state_machine.py")
verify=mod("verify","scripts/ao_mvp_verification_gate.py")
MATRIX=ROOT/"ops/authorizations/a1-authority-matrix.v1.json"
def _atomic(path:Path,obj:dict):
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix=path.name+".",dir=str(path.parent))
 try:
  with os.fdopen(fd,"w",encoding="utf-8") as h: json.dump(obj,h,sort_keys=True); h.write("\n"); h.flush(); os.fsync(h.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp): os.unlink(tmp)
def iterate(state_dir:Path):
 plan=selector.select()
 if not plan.get("selected_work_id"): return {"state":"idle","execution_performed":False}
 wid=plan["selected_work_id"]; state_path=state_dir/(wid.replace(":","_")+".json")
 if state_path.exists():
  existing=json.loads(state_path.read_text())
  if existing["state"] in sm.TERMINAL: return {"state":"terminal_noop","record":existing,"execution_performed":False}
 record=sm.new(wid); record=sm.transition(record,"selected","selector")
 matrix=json.loads(MATRIX.read_text())
 req={"work_id":wid,"capability":plan["capability"],"production":False,"mutation":False}
 decision=dispatcher.DispatchLedger().decide(req,matrix)
 if decision["decision"]!="allow_simulation":
  record=sm.transition(record,"policy_denied","dispatcher"); record=sm.transition(record,"blocked","dispatcher")
  _atomic(state_path,record); return {"state":"blocked","record":record,"execution_performed":False}
 dstore=ledger.DurableDispatchLedger(state_dir/"dispatch.jsonl")
 if dstore.contains(decision["dispatch_id"]):
  record=sm.transition(record,"policy_denied","durable_replay"); record=sm.transition(record,"blocked","durable_replay")
  _atomic(state_path,record); return {"state":"replay_blocked","record":record,"execution_performed":False}
 dstore.append_once(decision); record=sm.transition(record,"policy_allowed","dispatcher"); record=sm.transition(record,"dispatched_simulation","durable_dispatch"); record=sm.transition(record,"verification_pending","simulation")
 outcome={"work_id":wid,"execution_performed":False,"production_mutation":False,"adapter_status":"success","evidence_refs":[decision["dispatch_id"]],"checks_green":True}
 v=verify.verify(outcome)
 record=sm.transition(record,v["decision"],"verification_gate"); _atomic(state_path,record)
 return {"state":record["state"],"record":record,"verification":v,"execution_performed":False}

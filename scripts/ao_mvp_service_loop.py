#!/usr/bin/env python3
"""One bounded service tick: scheduler -> lease -> persistent planning loop."""
from __future__ import annotations
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);assert s and s.loader
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
sched=mod("sched","scripts/ao_mvp_scheduler_contract.py")
lease=mod("lease","scripts/ao_mvp_orchestrator_service_boundary.py")
runner=mod("runner","scripts/ao_mvp_persistent_loop_runner.py")
def tick(state_dir:Path,owner:str,epoch:int,schedule:dict)->dict:
 d=sched.due(schedule,epoch)
 if not d["due"]:return {"state":"not_due","execution_performed":False,"production_mutation":False}
 lp=state_dir/"service.lease";a=lease.acquire(lp,owner,epoch,120)
 if not a["acquired"]:return {"state":"lease_held","execution_performed":False,"production_mutation":False}
 try:
  result=runner.iterate(state_dir/"work")
  return {"state":"tick_complete","result":result,"execution_performed":False,"production_mutation":False}
 finally:
  lease.release(lp,owner)

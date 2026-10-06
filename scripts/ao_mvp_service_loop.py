#!/usr/bin/env python3
"""One bounded service tick: scheduler -> lease -> persistent planning loop."""
from __future__ import annotations
import json
import importlib.util
import os
import signal
import time
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
  if result.get("state") in {"success", "blocked", "replay_blocked", "terminal_noop", "idle"}:
   state_dir.mkdir(parents=True,exist_ok=True)
   schedule_path=state_dir/"schedule.json"
   tmp=schedule_path.with_suffix(".json.tmp")
   tmp.write_text(json.dumps({"interval_seconds":int(schedule["interval_seconds"]),"last_completed_epoch":epoch},sort_keys=True)+"\n",encoding="utf-8")
   os.replace(tmp,schedule_path)
  return {"state":"tick_complete","result":result,"execution_performed":False,"production_mutation":False}
 finally:
  lease.release(lp,owner)

def run()->None:
 """Run bounded local planning ticks; never performs provider or production I/O."""
 state_dir=Path(os.environ.get("PHIL_AI_OS_STATE_DIR","/var/lib/phil-ai-os/ao-mvp"))
 interval=int(os.environ.get("PHIL_AI_OS_INTERVAL_SECONDS","300"))
 if interval<sched.MIN_INTERVAL:
  raise SystemExit(f"PHIL_AI_OS_INTERVAL_SECONDS must be >= {sched.MIN_INTERVAL}")
 owner=os.environ.get("HOSTNAME","ao-mvp-orchestrator")
 stop=False
 def request_stop(_signum,_frame):
  nonlocal stop
  stop=True
 signal.signal(signal.SIGTERM,request_stop)
 signal.signal(signal.SIGINT,request_stop)
 while not stop:
  schedule_path=state_dir/"schedule.json"
  schedule={"interval_seconds":interval,"last_completed_epoch":None}
  if schedule_path.exists():
   try:
    saved=json.loads(schedule_path.read_text(encoding="utf-8"))
    schedule["last_completed_epoch"]=saved.get("last_completed_epoch")
   except (OSError,ValueError,AttributeError):
    # Corrupt scheduling state fails closed; it is preserved for investigation.
    print(json.dumps({"state":"schedule_state_invalid","execution_performed":False,"production_mutation":False}),flush=True)
    time.sleep(interval)
    continue
  now=int(time.time())
  result=tick(state_dir,owner,now,schedule)
  print(json.dumps({"state":result.get("state"),"execution_performed":False,"production_mutation":False}),flush=True)
  for _ in range(interval):
   if stop:break
   time.sleep(1)

if __name__=="__main__":
 run()

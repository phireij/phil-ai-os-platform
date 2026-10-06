#!/usr/bin/env python3
"""AO-4 persistent orchestrator state-machine contract.

Pure transition engine: no provider calls, repository mutation, production
mutation, messaging, payments, merges, or timers.
"""
from __future__ import annotations
from typing import Any
TERMINAL={"verified_success","failed","blocked","escalated"}
ALLOWED={
 "queued":{"selected","blocked"},
 "selected":{"policy_allowed","policy_denied"},
 "policy_allowed":{"dispatched_simulation","blocked"},
 "policy_denied":{"blocked","escalated"},
 "dispatched_simulation":{"verification_pending"},
 "verification_pending":{"verified_success","failed","escalated"},
}
def transition(record:dict[str,Any],event:str,evidence_ref:str)->dict[str,Any]:
 cur=record["state"]
 if cur in TERMINAL: raise ValueError("terminal state is immutable")
 if event not in ALLOWED.get(cur,set()): raise ValueError("invalid transition")
 history=list(record.get("history",[]))
 history.append({"from":cur,"to":event,"evidence_ref":evidence_ref})
 return {**record,"state":event,"history":history,"execution_performed":False,"production_mutation":False}
def new(work_id:str)->dict[str,Any]:
 return {"schema":"phil-ai-os-orchestrator-state","version":1,"work_id":work_id,"state":"queued","history":[],"execution_performed":False,"production_mutation":False}

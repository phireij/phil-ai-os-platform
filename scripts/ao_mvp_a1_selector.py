#!/usr/bin/env python3
"""Active A1 bounded selector. Returns a plan only; dispatcher separately enforces capability/side-effect policy."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
Q=ROOT/"ops/autonomous-work-queue/work-queue.v1.json"
M=ROOT/"ops/authorizations/a1-authority-matrix.v1.json"
CAP={
 "ao-work:ao5-mission-control-projection":"tests_static_analysis",
 "ao-work:ruby-readiness-reconcile":"status_reconciliation",
 "ao-work:kcfc-readonly-adapter":"read_only_staging_evidence_collection",
 "ao-work:ao4-synthetic-orchestrator":"tests_static_analysis",
 "ao-work:master-status-regeneration":"status_reconciliation",
 "ao-work:orchestrator-state-machine":"tests_static_analysis",
 "ao-work:persistent-loop-runner":"development_branch_code_preparation",
 "ao-work:orchestrator-service-boundary":"development_branch_code_preparation",
 "ao-work:service-heartbeat-recovery":"development_branch_code_preparation",
 "ao-work:scheduler-contract":"development_branch_code_preparation",
 "ao-work:service-loop-composition":"development_branch_code_preparation",
 "ao-work:runtime-deployment-plan":"documentation",
 "ao-work:runtime-package-contract":"development_branch_code_preparation",
 "ao-work:runtime-state-integrity":"tests_static_analysis",
 "ao-work:runtime-rollback-drill":"tests_static_analysis",
 "ao-work:hosted-runtime-readiness-record":"status_reconciliation",
 "ao-work:deployment-gate-package":"documentation",
 "ao-work:predeployment-acceptance-summary":"documentation",
 "ao-work:runtime-target-decision-package":"documentation",
 "ao-work:ao4-verification-gate":"tests_static_analysis",
 "ao-work:ao4-approval-escalation":"documentation",
 "ao-work:orchestrator-state-machine":"tests_static_analysis",
 "ao-work:persistent-loop-runner":"development_branch_code_preparation"
}
def load(p:Path)->dict[str,Any]: return json.loads(p.read_text())
def select()->dict[str,Any]:
 q=load(Q); m=load(M)
 if m.get("activation_state")!="active" or m.get("effective_autonomy_ceiling")!="A1":
  return {"selected_work_id":None,"reason":"A1 not active","execution_authorized":False,"authority_effect":"none"}
 if m.get("production_mutation_authorized") is not False:
  return {"selected_work_id":None,"reason":"fail closed: production mutation boundary invalid","execution_authorized":False,"authority_effect":"none"}
 items=q.get("items") or []; by={i["work_id"]:i for i in items}
 completed={i["work_id"] for i in items if i.get("state")=="completed"}
 eligible=[]
 for i in items:
  if i.get("state")!="ready_for_inert_selection" or not (i.get("selection") or {}).get("eligible"): continue
  if any(d not in completed for d in i.get("dependencies",[])): continue
  if i["work_id"] not in CAP: continue
  eligible.append(i)
 eligible.sort(key=lambda x:(x["priority"],x["work_id"]))
 chosen=eligible[0] if eligible else None
 return {"selected_work_id":chosen["work_id"] if chosen else None,"capability":CAP.get(chosen["work_id"]) if chosen else None,
 "reason":"bounded A1 candidate selected for dispatcher policy check" if chosen else "no bounded A1 candidate",
 "execution_authorized":False,"authority_effect":"none","production":False,"mutation":False}
if __name__=="__main__": print(json.dumps(select(),sort_keys=True))

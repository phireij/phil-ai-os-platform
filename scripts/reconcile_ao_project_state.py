#!/usr/bin/env python3
"""AO-1 deterministic project-state reconciler from explicit committed observations."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"ops/project-registry/project-registry.v1.json"
OBS_DIR=ROOT/"ops/project-state/observations"

def load(path:Path)->dict[str,Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def observations()->dict[str,list[dict[str,Any]]]:
    out:dict[str,list[dict[str,Any]]]={}
    for path in sorted(OBS_DIR.glob("*.json")):
        o=load(path)
        if o.get("authority")!={"authority_effect":"none","mutation_authorized":False}:
            continue
        out.setdefault(o["project_id"],[]).append({**o,"_ref":str(path.relative_to(ROOT))})
    return out

def ev(o:dict[str,Any])->dict[str,str]:
    return {"kind":o["source_kind"],"ref":o["_ref"],"observed_at":o["observed_at"],"freshness":o["freshness"]}

def base(p:dict[str,Any], obs:list[dict[str,Any]])->dict[str,Any]:
    return {
      "schema_version":1,"project_id":p["project_id"],"objective":p["current_objective"],
      "milestone":"AO-1 evidence reconciliation","status":"unknown",
      "repository_state":{"repository":p["repository"],"ref":p["default_branch"],"verified_head":p["verified_head"],"verified_at":p["verified_at"]},
      "deployment_state":{"status":"unknown","verified_at":None,"environment":None,"evidence_ref":None},
      "completed":[],"in_progress":[],"queue":[],"blockers":[],"approvals_required":[],
      "agent_activity":[],"next_actions":[],"evidence":[ev(o) for o in obs],
      "authority":{"autonomy_ceiling":"A0","mutation_authorized":False}
    }

def reconcile(p:dict[str,Any], obs:list[dict[str,Any]])->dict[str,Any]:
    s=base(p,obs); pid=p["project_id"]
    fresh=[o for o in obs if o.get("freshness")=="fresh"]
    if pid=="phil-ai-os":
        ci=next((o for o in fresh if o["source_kind"]=="github_ci"),None)
        if ci and ci["facts"].get("contract_ci")=="success" and ci["facts"].get("supply_chain")=="success":
            s["status"]="green"; s["completed"]=["Bounded A1 contract and exact-head CI evidenced GREEN"]
        else:
            s["status"]="unknown"; s["blockers"]=["Fresh successful AO-MVP CI evidence is missing"]
        s["in_progress"]=["Persistent autonomous operations MVP"]
        s["next_actions"]=["Continue bounded A1 engineering from durable queue"]
    elif pid=="rubys-cake-delights-hq":
        ready=next((o for o in obs if o["source_kind"]=="committed_readiness"),None)
        if ready is None:
            s["status"]="unknown"; s["blockers"]=["Ruby readiness evidence is missing"]
        elif ready["freshness"]!="fresh":
            s["status"]="yellow"; s["blockers"]=["Ruby readiness evidence is stale and cannot support GREEN"]
        elif ready["facts"].get("production_activation_ready") is False:
            s["status"]="yellow"; s["blockers"]=["Quick Pickup production activation readiness is false"]
        else:
            s["status"]="green"
        if ready and ready["facts"].get("production_activation_ready") is False and "Quick Pickup production activation readiness is false" not in s["blockers"]:
            s["blockers"].append("Quick Pickup production activation readiness is false")
        s["approvals_required"]=["Production publish remains separately gated"]
        s["in_progress"]=["Refresh Ruby readiness evidence through read-only adapter"]
        s["next_actions"]=["Reconcile eligible catalog and Quick Pickup readiness evidence"]
    elif pid=="kcfc-portal":
        repo=next((o for o in fresh if o["source_kind"]=="repository_snapshot"),None)
        if repo:
            facts=repo["facts"]; s["status"]="yellow"
            s["repository_state"]["ref"]=facts.get("development_branch",p.get("development_branch",p["default_branch"]))
            s["repository_state"]["verified_head"]=facts.get("development_head",p.get("verified_development_head",p["verified_head"]))
            s["completed"]=["Fresh read-only repository snapshot observed"]
            s["blockers"]=["Fresh staging runtime evidence is not yet represented"]
        else:
            s["status"]="unknown"; s["blockers"]=["Fresh KCFC repository evidence is missing"]
        s["in_progress"]=["Read-only KCFC evidence integration"]
        s["next_actions"]=["Add read-only staging evidence observation"]
    return s

def build()->dict[str,Any]:
    registry=load(REGISTRY); by_project=observations()
    states=[reconcile(p,by_project.get(p["project_id"],[])) for p in sorted(registry["projects"],key=lambda x:x["priority"])]
    return {"schema":"phil-ai-os-master-project-status","version":1,"authority_effect":"none","autonomy_ceiling":"A0","projects":states}

def main()->None:
    print(json.dumps(build(),indent=2,sort_keys=True))
if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""Ruby read-only readiness adapter: converts committed readiness into an AO observation."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"ops/readiness/ruby-first-party-quick-pickup-readiness.json"
def build():
 r=json.loads(SRC.read_text())
 pr=r["production_readiness"]; auth=r["authority"]
 blockers=[k for k,v in pr.items() if k!="production_activation_ready" and v is False]
 return {
  "schema":"phil-ai-os-project-observation","version":1,"project_id":"rubys-cake-delights-hq",
  "source_kind":"committed_readiness","observed_at":r["date"],"freshness":"stale",
  "facts":{
   "decision":r["decision"],"production_activation_ready":pr["production_activation_ready"],
   "unmet_readiness_controls":sorted(blockers),
   "customer_order_creation_authorized":auth["customer_order_creation_authorized"],
   "inventory_mutation_authorized":auth["inventory_mutation_authorized"],
   "automatic_production_execution_authorized":auth["automatic_production_execution_authorized"]
  },
  "authority":{"authority_effect":"none","mutation_authorized":False}
 }
if __name__=="__main__": print(json.dumps(build(),indent=2,sort_keys=True))

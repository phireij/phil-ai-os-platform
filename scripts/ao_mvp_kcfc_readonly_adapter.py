#!/usr/bin/env python3
"""KCFC read-only repository observation adapter from the canonical project registry."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/"ops/project-registry/project-registry.v1.json"
def build():
 reg=json.loads(REG.read_text()); p=next(x for x in reg["projects"] if x["project_id"]=="kcfc-portal")
 return {
  "schema":"phil-ai-os-project-observation","version":1,"project_id":"kcfc-portal",
  "source_kind":"repository_snapshot","observed_at":p["verified_at"],"freshness":"fresh",
  "facts":{"repository":p["repository"],"main_head":p["verified_head"],"development_branch":p["development_branch"],
   "development_head":p["verified_development_head"],"integration_mode":"read_only","production_mutation_authorized":False},
  "authority":{"authority_effect":"none","mutation_authorized":False}
 }
if __name__=="__main__": print(json.dumps(build(),indent=2,sort_keys=True))

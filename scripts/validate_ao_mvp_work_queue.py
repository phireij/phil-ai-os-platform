#!/usr/bin/env python3
"""Fail-closed validation for the AO-MVP A0 durable work queue."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/"ops/autonomous-work-queue/work-queue.v1.json"
EXPECTED={"phil-ai-os","rubys-cake-delights-hq","kcfc-portal"}

def require(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit("AO-MVP work queue validation failed: "+msg)

def main() -> None:
    data=json.loads(QUEUE.read_text(encoding="utf-8"))
    require(data.get("schema")=="phil-ai-os-autonomous-work-queue","schema")
    require(data.get("version")==1,"version")
    require(data.get("authority_effect")=="none","authority effect")
    require(data.get("autonomy_ceiling")=="A0","autonomy ceiling")
    require(data.get("execution_enabled") is False,"execution must remain disabled")
    items=data.get("items")
    require(isinstance(items,list) and items,"items")
    ids=[i.get("work_id") for i in items]
    require(len(ids)==len(set(ids)),"work IDs must be unique")
    known=set(ids)
    for item in items:
        require(item.get("project_id") in EXPECTED,"unknown project")
        auth=item.get("authority") or {}
        require(auth=={"autonomy_ceiling":"A0","authority_effect":"none","mutation_authorized":False,"automatic_execution":False},"authority contract")
        selection=item.get("selection") or {}
        require(selection.get("execution_authorized") is False,"selection cannot authorize execution")
        for dep in item.get("dependencies",[]):
            require(dep in known,"unknown dependency")
    a1=next((i for i in items if i.get("work_id")=="ao-work:a1-activation"),None)
    require(a1 is not None,"A1 gate item missing")
    require(a1.get("state")=="awaiting_ceo_approval","A1 must await CEO approval")
    require((a1.get("selection") or {}).get("eligible") is False,"A1 cannot be selector eligible")
    print("AO-MVP A0 durable work queue: GREEN")

if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""AO-3 deterministic inert selector. It selects; it never executes."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/"ops/autonomous-work-queue/work-queue.v1.json"
MATRIX=ROOT/"ops/authorizations/a1-authority-matrix.v1.json"

def load(p: Path) -> dict[str,Any]:
    return json.loads(p.read_text(encoding="utf-8"))

def select() -> dict[str,Any]:
    queue=load(QUEUE); matrix=load(MATRIX)
    if queue.get("execution_enabled") is not False:
        raise SystemExit("fail closed: queue execution flag must be false")
    if matrix.get("effective_autonomy_ceiling") != "A0":
        raise SystemExit("fail closed: selector is pre-activation and requires A0")
    items=queue.get("items") or []
    by_id={i["work_id"]:i for i in items}
    completed={i["work_id"] for i in items if i.get("state")=="completed"}
    candidates=[]
    for item in items:
        if item.get("state")!="ready_for_inert_selection":
            continue
        if (item.get("selection") or {}).get("execution_authorized") is not False:
            raise SystemExit("fail closed: item attempted execution authorization")
        auth=item.get("authority") or {}
        if auth.get("authority_effect")!="none" or auth.get("mutation_authorized") is not False:
            raise SystemExit("fail closed: item authority violation")
        deps=item.get("dependencies") or []
        if any(d not in by_id for d in deps):
            raise SystemExit("fail closed: unknown dependency")
        if any(d not in completed for d in deps):
            continue
        candidates.append(item)
    candidates.sort(key=lambda i:(i["priority"],i["work_id"]))
    chosen=candidates[0] if candidates else None
    return {
        "schema":"phil-ai-os-inert-selector-result","version":1,
        "selected_work_id":chosen["work_id"] if chosen else None,
        "candidate_count":len(candidates),
        "execution_authorized":False,
        "mutation_authorized":False,
        "authority_effect":"none",
        "reason":"lowest priority number among dependency-satisfied inert candidates" if chosen else "no eligible inert candidate"
    }

if __name__=="__main__":
    print(json.dumps(select(),sort_keys=True))

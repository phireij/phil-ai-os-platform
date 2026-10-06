#!/usr/bin/env python3
"""Read-only health/readiness projection for the bounded orchestrator runtime."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any
def project(state:dict[str,Any])->dict[str,Any]:
 checks={"state_volume_readable":state.get("state_volume_readable") is True,"authority_matrix_loaded":state.get("authority_matrix_loaded") is True,"lease_backend_ready":state.get("lease_backend_ready") is True,"denylist_loaded":state.get("denylist_loaded") is True}
 ready=all(checks.values())
 return {"status":"ready" if ready else "not_ready","checks":checks,"authority_effect":"none","mutation_authorized":False,"production_mutation":False}

def main()->None:
 state_dir=Path(os.environ.get("PHIL_AI_OS_STATE_DIR","/var/lib/phil-ai-os/ao-mvp"))
 state={
  "state_volume_readable":state_dir.is_dir() and os.access(state_dir,os.R_OK),
  "authority_matrix_loaded":(state_dir/"authority.json").is_file(),
  "lease_backend_ready":(state_dir/"service.lease").parent==state_dir,
  "denylist_loaded":(state_dir/"denylist.json").is_file(),
 }
 print(json.dumps(project(state),sort_keys=True),flush=True)

if __name__=="__main__":
 main()

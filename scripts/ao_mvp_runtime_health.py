#!/usr/bin/env python3
"""Read-only health/readiness projection for the bounded orchestrator runtime."""
from __future__ import annotations
from typing import Any
def project(state:dict[str,Any])->dict[str,Any]:
 checks={"state_volume_readable":state.get("state_volume_readable") is True,"authority_matrix_loaded":state.get("authority_matrix_loaded") is True,"lease_backend_ready":state.get("lease_backend_ready") is True,"denylist_loaded":state.get("denylist_loaded") is True}
 ready=all(checks.values())
 return {"status":"ready" if ready else "not_ready","checks":checks,"authority_effect":"none","mutation_authorized":False,"production_mutation":False}

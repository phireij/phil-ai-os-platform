#!/usr/bin/env python3
"""AO-4 bounded dispatcher simulation.

Produces durable dispatch decisions only. No provider, repository, production,
messaging, payment, or merge action is callable from this module.
"""
from __future__ import annotations
import hashlib, json
from typing import Any

ALLOWED={
 "repository_inspection","status_reconciliation","tests_static_analysis",
 "documentation","development_branch_code_preparation","ci_execution",
 "ci_failure_investigation","draft_pull_request_preparation",
 "read_only_staging_evidence_collection"
}

class DispatchLedger:
    def __init__(self) -> None:
        self._seen:set[str]=set()

    def decide(self, request:dict[str,Any], matrix:dict[str,Any]) -> dict[str,Any]:
        material=json.dumps(request,sort_keys=True,separators=(",",":"))
        dispatch_id="a1-dispatch:"+hashlib.sha256(material.encode()).hexdigest()[:24]
        base={"schema":"phil-ai-os-a1-dispatch-decision","version":1,"dispatch_id":dispatch_id,
              "execution_performed":False,"production_mutation":False}
        if dispatch_id in self._seen:
            return {**base,"decision":"deny","reason":"replay","replay":True}
        self._seen.add(dispatch_id)
        if matrix.get("activation_state") not in {"preauthorized_pending_preconditions","active"}:
            return {**base,"decision":"deny","reason":"activation_state_invalid","replay":False}
        capability=request.get("capability")
        if capability in set(matrix.get("denied_capabilities") or []):
            return {**base,"decision":"deny","reason":"explicit_denylist","replay":False}
        if capability not in ALLOWED or capability not in set(matrix.get("allowlisted_capabilities") or []):
            return {**base,"decision":"deny","reason":"not_allowlisted","replay":False}
        if request.get("production") is not False or request.get("mutation") is not False:
            return {**base,"decision":"deny","reason":"side_effect_boundary","replay":False}
        return {**base,"decision":"allow_simulation","reason":"bounded_a1_allowlist","replay":False}

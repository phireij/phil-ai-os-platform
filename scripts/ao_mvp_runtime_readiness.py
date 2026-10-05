#!/usr/bin/env python3
"""Pre-deployment fail-closed readiness evaluator for hosted AO-MVP runtime."""
from __future__ import annotations
REQUIRED=("persistent_volume","single_worker_exclusion","corrupt_state_fail_closed","log_redaction","egress_policy","a1_denylist","rollback","exact_revision_ci")
def evaluate(evidence:dict)->dict:
 missing=[k for k in REQUIRED if evidence.get(k) is not True]
 return {"schema":"phil-ai-os-hosted-runtime-readiness","version":1,"ready":not missing,"missing":missing,"deployment_authorized":False,"authority_effect":"none","production_mutation":False}

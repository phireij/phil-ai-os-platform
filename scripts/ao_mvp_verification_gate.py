#!/usr/bin/env python3
"""Independent verification gate for bounded AO-MVP outcomes."""
from __future__ import annotations
from typing import Any
def verify(outcome:dict[str,Any])->dict[str,Any]:
 base={"schema":"phil-ai-os-verification-decision","version":1,"work_id":outcome.get("work_id"),"authority_effect":"none","production_mutation":False}
 if outcome.get("execution_performed") is not False or outcome.get("production_mutation") is not False:
  return {**base,"decision":"failed","reason":"side_effect_boundary"}
 if outcome.get("adapter_status") in {None,"unknown","error","failed"}:
  return {**base,"decision":"failed","reason":"adapter_not_verified"}
 refs=outcome.get("evidence_refs") or []
 if not refs:
  return {**base,"decision":"failed","reason":"missing_evidence"}
 if outcome.get("checks_green") is not True:
  return {**base,"decision":"failed","reason":"checks_not_green"}
 return {**base,"decision":"verified_success","reason":"independent_checks_green","evidence_refs":refs}

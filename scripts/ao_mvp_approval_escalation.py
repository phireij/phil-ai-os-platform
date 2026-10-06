#!/usr/bin/env python3
"""Deterministic escalation formatter. It cannot approve, execute, or widen authority."""
from __future__ import annotations
from typing import Any
def escalate(work:dict[str,Any], reason:str)->dict[str,Any]:
 return {"schema":"phil-ai-os-approval-escalation","version":1,"work_id":work.get("work_id"),
 "project_id":work.get("project_id"),"state":"awaiting_explicit_approval","reason":reason,
 "authority_effect":"none","approval_granted":False,"execution_authorized":False,"production_mutation":False}

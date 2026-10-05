#!/usr/bin/env python3
"""Pure A1 rollback transform. Returns A0 state; performs no side effects."""
from __future__ import annotations
from copy import deepcopy
from typing import Any

def rollback(matrix:dict[str,Any]) -> dict[str,Any]:
    out=deepcopy(matrix)
    out["activation_state"]="rolled_back_to_a0"
    out["effective_autonomy_ceiling"]="A0"
    out["automatic_execution_enabled"]=False
    out["production_mutation_authorized"]=False
    out["authority_effect"]="none"
    out["rollback"]={"performed":True,"production_mutation":False,"history_preserved":True}
    return out

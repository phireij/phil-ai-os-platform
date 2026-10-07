#!/usr/bin/env python3
"""Synthetic rollback-plan contract for future public webhook activation."""

REQUIRED_ACTIONS=(
 "disable_ingress",
 "remove_dedicated_route",
 "close_dedicated_public_port",
 "preserve_private_a1_runtime",
 "preserve_evidence",
)

def validate_rollback(plan: dict):
    errors=[]
    if plan.get("authority_effect")!="none": errors.append("authority effect must remain none")
    if plan.get("production_mutation") is not False: errors.append("production mutation forbidden")
    if plan.get("touch_hermes") is not False: errors.append("Hermes must remain untouched")
    actions=plan.get("actions",[])
    if actions != list(REQUIRED_ACTIONS): errors.append("rollback actions must be exact and ordered")
    if plan.get("fail_closed_on_unknown") is not True: errors.append("unknown state must fail closed")
    return errors

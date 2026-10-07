#!/usr/bin/env python3
"""Validate that a proposed future public-webhook plan is isolated.

Repository-only planning validator: it never changes DNS, routes, ports or hosts.
"""
FORBIDDEN_HOST_FRAGMENTS=("hermes",)
FORBIDDEN_SHARED_COMPONENTS=("hermes","traefik-existing","phil-ai-os-core")

def validate_plan(plan: dict):
    errors=[]
    if plan.get("apply_changes") is not False:
        errors.append("plan must be non-applying")
    host=plan.get("dedicated_hostname")
    if host is not None:
        h=str(host).lower()
        if any(x in h for x in FORBIDDEN_HOST_FRAGMENTS):
            errors.append("Hermes hostname reuse forbidden")
    shared=set(plan.get("shared_components",[]))
    overlap=shared.intersection(FORBIDDEN_SHARED_COMPONENTS)
    if overlap:
        errors.append("shared existing workload forbidden: "+",".join(sorted(overlap)))
    if plan.get("production_credentials") not in (None,False):
        errors.append("production credentials forbidden")
    if plan.get("production_mutation_capability") not in (None,False):
        errors.append("production mutation capability forbidden")
    if plan.get("public_webhook_activation_authorized") is not False:
        errors.append("public activation must remain false")
    if plan.get("authority_effect")!="none":
        errors.append("authority effect must remain none")
    return errors

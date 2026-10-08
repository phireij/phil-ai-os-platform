#!/usr/bin/env python3
"""Allowlist-only structured logging for synthetic AO-MVP webhook ingress."""

ALLOWED_FIELDS=("request_id","event_id_hash","kind","decision","reason","status_code","authority_effect")
ALLOWED_KINDS=("synthetic_canary",)
ALLOWED_DECISIONS=("accepted","rejected")

def sanitize_webhook_log(event: dict) -> dict:
    out={}
    for key in ALLOWED_FIELDS:
        if key in event:
            out[key]=event[key]
    if out.get("kind") not in ALLOWED_KINDS:
        out.pop("kind",None)
    if out.get("decision") not in ALLOWED_DECISIONS:
        out["decision"]="rejected"
    out["authority_effect"]="none"
    return out

#!/usr/bin/env python3
"""Minimal structured-log redaction contract for AO-MVP runtime."""
from __future__ import annotations
SENSITIVE=("token","secret","password","authorization","cookie","customer_email","customer_phone")
def sanitize(event:dict)->dict:
 out={}
 for k,v in event.items():
  lk=k.lower()
  out[k]="[REDACTED]" if any(s in lk for s in SENSITIVE) else v
 out["authority_effect"]="none";return out

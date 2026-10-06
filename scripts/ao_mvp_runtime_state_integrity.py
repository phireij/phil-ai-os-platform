#!/usr/bin/env python3
"""Fail-closed integrity checks for persisted AO-MVP runtime state."""
from __future__ import annotations
import hashlib,json
from typing import Any
def canonical(obj:dict[str,Any])->bytes:return json.dumps(obj,sort_keys=True,separators=(",",":")).encode()
def envelope(payload:dict[str,Any])->dict[str,Any]:
 return {"schema":"phil-ai-os-runtime-state-envelope","version":1,"payload":payload,"sha256":hashlib.sha256(canonical(payload)).hexdigest()}
def verify(obj:dict[str,Any])->dict[str,Any]:
 if obj.get("schema")!="phil-ai-os-runtime-state-envelope" or obj.get("version")!=1:return {"valid":False,"reason":"schema","authority_effect":"none"}
 p=obj.get("payload");h=obj.get("sha256")
 if not isinstance(p,dict) or not isinstance(h,str):return {"valid":False,"reason":"shape","authority_effect":"none"}
 ok=hashlib.sha256(canonical(p)).hexdigest()==h
 return {"valid":ok,"reason":"ok" if ok else "checksum","authority_effect":"none","execution_authorized":False}

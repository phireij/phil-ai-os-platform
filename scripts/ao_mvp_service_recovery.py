#!/usr/bin/env python3
"""Heartbeat and crash-recovery semantics for the bounded orchestrator lease."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
def heartbeat(lease:dict[str,Any],owner:str,epoch:int,ttl:int)->dict[str,Any]:
 if ttl<1: raise ValueError("ttl")
 if lease.get("owner")!=owner: return {"renewed":False,"reason":"owner_mismatch","authority_effect":"none"}
 if int(lease.get("expires_epoch",0))<=epoch: return {"renewed":False,"reason":"expired","authority_effect":"none"}
 renewed={**lease,"expires_epoch":epoch+ttl,"last_heartbeat_epoch":epoch,"authority_effect":"none","production_mutation":False}
 return {"renewed":True,"lease":renewed,"authority_effect":"none"}
def recovery_decision(lease_path:Path,epoch:int)->dict[str,Any]:
 if not lease_path.exists(): return {"recoverable":True,"reason":"no_lease","authority_effect":"none"}
 lease=json.loads(lease_path.read_text())
 if int(lease.get("expires_epoch",0))<=epoch: return {"recoverable":True,"reason":"expired_lease","authority_effect":"none"}
 return {"recoverable":False,"reason":"active_lease","authority_effect":"none"}

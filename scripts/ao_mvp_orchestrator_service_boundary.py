#!/usr/bin/env python3
"""Restart-safe single-worker lease contract for the bounded local orchestrator."""
from __future__ import annotations
import json,os,tempfile
from pathlib import Path
from typing import Any
def _write(path:Path,obj:dict[str,Any]):
 path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix=path.name+".",dir=str(path.parent))
 try:
  with os.fdopen(fd,"w",encoding="utf-8") as h: json.dump(obj,h,sort_keys=True); h.write("\n"); h.flush(); os.fsync(h.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp): os.unlink(tmp)
def acquire(path:Path,owner:str,epoch:int,ttl:int)->dict[str,Any]:
 if ttl<1: raise ValueError("ttl")
 if path.exists():
  cur=json.loads(path.read_text())
  if int(cur["expires_epoch"])>epoch and cur["owner"]!=owner:
   return {"acquired":False,"reason":"lease_held","authority_effect":"none"}
 lease={"schema":"phil-ai-os-orchestrator-lease","version":1,"owner":owner,"acquired_epoch":epoch,"expires_epoch":epoch+ttl,"authority_effect":"none","production_mutation":False}
 _write(path,lease); return {"acquired":True,"lease":lease,"authority_effect":"none"}
def release(path:Path,owner:str)->bool:
 if not path.exists(): return True
 cur=json.loads(path.read_text())
 if cur["owner"]!=owner: return False
 path.unlink(); return True

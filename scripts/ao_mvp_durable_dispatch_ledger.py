#!/usr/bin/env python3
"""AO-4 durable append-only dispatch-decision ledger for bounded A1 planning.

Writes only to a caller-supplied local ledger path. It never invokes providers,
GitHub mutations, production systems, messaging, payments, or merge actions.
"""
from __future__ import annotations
import hashlib,json,os,tempfile
from pathlib import Path
from typing import Any

def dispatch_id(request:dict[str,Any])->str:
 material=json.dumps(request,sort_keys=True,separators=(",",":"))
 return "a1-dispatch:"+hashlib.sha256(material.encode()).hexdigest()[:24]

class DurableDispatchLedger:
 def __init__(self,path:Path)->None: self.path=path
 def _read(self)->list[dict[str,Any]]:
  if not self.path.exists(): return []
  rows=[]
  for line in self.path.read_text(encoding="utf-8").splitlines():
   if line.strip(): rows.append(json.loads(line))
  return rows
 def contains(self,did:str)->bool:
  return any(r.get("dispatch_id")==did for r in self._read())
 def append_once(self,decision:dict[str,Any])->bool:
  did=decision["dispatch_id"]
  if self.contains(did): return False
  self.path.parent.mkdir(parents=True,exist_ok=True)
  existing=self.path.read_text(encoding="utf-8") if self.path.exists() else ""
  payload=existing+json.dumps(decision,sort_keys=True,separators=(",",":"))+"\n"
  fd,tmp=tempfile.mkstemp(prefix=self.path.name+".",dir=str(self.path.parent))
  try:
   with os.fdopen(fd,"w",encoding="utf-8") as h:
    h.write(payload); h.flush(); os.fsync(h.fileno())
   os.replace(tmp,self.path)
  finally:
   if os.path.exists(tmp): os.unlink(tmp)
  return True

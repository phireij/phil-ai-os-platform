#!/usr/bin/env python3
"""Restart-safe single-worker lease contract for the bounded local orchestrator."""
from __future__ import annotations
import json,os,tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any,Iterator

if os.name=="nt":
 import msvcrt
else:
 import fcntl

_guard_registry_lock=Lock()
_guard_registry:dict[str,Lock]={}

@contextmanager
def _exclusive_guard(path:Path)->Iterator[None]:
 guard_path=path.with_name(path.name+".guard")
 guard_path.parent.mkdir(parents=True,exist_ok=True)
 key=str(guard_path.resolve())
 with _guard_registry_lock:
  thread_guard=_guard_registry.setdefault(key,Lock())
 thread_guard.acquire()
 try:
  with guard_path.open("a+b") as guard:
   if os.name=="nt":
    guard.seek(0,os.SEEK_END)
    if guard.tell()==0:
     guard.write(b"\0");guard.flush()
    guard.seek(0)
    msvcrt.locking(guard.fileno(),msvcrt.LK_LOCK,1)
   else:
    fcntl.flock(guard.fileno(),fcntl.LOCK_EX)
   try:
    yield
   finally:
    if os.name=="nt":
     guard.seek(0)
     msvcrt.locking(guard.fileno(),msvcrt.LK_UNLCK,1)
    else:
     fcntl.flock(guard.fileno(),fcntl.LOCK_UN)
 finally:
  thread_guard.release()

def _write(path:Path,obj:dict[str,Any]):
 path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix=path.name+".",dir=str(path.parent))
 try:
  with os.fdopen(fd,"w",encoding="utf-8") as h: json.dump(obj,h,sort_keys=True); h.write("\n"); h.flush(); os.fsync(h.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp): os.unlink(tmp)
def acquire(path:Path,owner:str,epoch:int,ttl:int)->dict[str,Any]:
 if ttl<1: raise ValueError("ttl")
 with _exclusive_guard(path):
  if path.exists():
   cur=json.loads(path.read_text())
   if int(cur["expires_epoch"])>epoch:
    return {"acquired":False,"reason":"lease_held","authority_effect":"none"}
  lease={"schema":"phil-ai-os-orchestrator-lease","version":1,"owner":owner,"acquired_epoch":epoch,"expires_epoch":epoch+ttl,"authority_effect":"none","production_mutation":False}
  _write(path,lease)
  return {"acquired":True,"lease":lease,"authority_effect":"none"}
def release(path:Path,owner:str)->bool:
 with _exclusive_guard(path):
  if not path.exists(): return True
  cur=json.loads(path.read_text())
  if cur["owner"]!=owner: return False
  path.unlink()
  return True

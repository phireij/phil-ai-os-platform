#!/usr/bin/env python3
import importlib.util,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/"scripts/ao_mvp_service_recovery.py"
s=importlib.util.spec_from_file_location("x",p);assert s and s.loader;m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
lease={"owner":"a","expires_epoch":130,"authority_effect":"none","production_mutation":False}
r=m.heartbeat(lease,"a",110,30);assert r["renewed"] and r["lease"]["expires_epoch"]==140
assert m.heartbeat(lease,"b",110,30)["renewed"] is False
assert m.heartbeat(lease,"a",131,30)["renewed"] is False
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/"lease.json";assert m.recovery_decision(p,100)["recoverable"] is True
 p.write_text(json.dumps(lease));assert m.recovery_decision(p,120)["recoverable"] is False
 assert m.recovery_decision(p,131)["recoverable"] is True
print("AO-4 heartbeat/crash-recovery contract: GREEN")

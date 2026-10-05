#!/usr/bin/env python3
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/"scripts/ao_mvp_runtime_state_integrity.py";s=importlib.util.spec_from_file_location("x",p);assert s and s.loader;m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
e=m.envelope({"state":"queued","work_id":"x"});assert m.verify(e)["valid"] is True
e["payload"]["state"]="verified_success";r=m.verify(e);assert r["valid"] is False and r["execution_authorized"] is False
assert m.verify({"schema":"bad"})["valid"] is False
print("AO-MVP runtime state-integrity contract: GREEN")

#!/usr/bin/env python3
import importlib.util,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"scripts/ao_mvp_persistent_loop_runner.py"
s=importlib.util.spec_from_file_location("r",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
with tempfile.TemporaryDirectory() as td:
 d=Path(td)
 a=m.iterate(d)
 assert a["state"]=="verified_success"
 assert a["execution_performed"] is False
 b=m.iterate(d)
 assert b["state"]=="terminal_noop"
 assert b["execution_performed"] is False
 assert len((d/"dispatch.jsonl").read_text().splitlines())==1
print("AO-4 persistent local loop runner: GREEN")

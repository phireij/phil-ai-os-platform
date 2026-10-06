#!/usr/bin/env python3
import importlib.util,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/"scripts/ao_mvp_service_loop.py";s=importlib.util.spec_from_file_location("x",p);assert s and s.loader;m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
with tempfile.TemporaryDirectory() as td:
 d=Path(td)
 a=m.tick(d,"worker",100,{"interval_seconds":60,"last_completed_epoch":100});assert a["state"]=="not_due"
 b=m.tick(d,"worker",160,{"interval_seconds":60,"last_completed_epoch":100});assert b["state"]=="tick_complete";assert b["execution_performed"] is False and b["production_mutation"] is False
 assert not (d/"service.lease").exists()
print("AO-4 bounded service-loop composition: GREEN")

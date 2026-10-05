#!/usr/bin/env python3
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/"scripts/ao_mvp_scheduler_contract.py";s=importlib.util.spec_from_file_location("x",p);assert s and s.loader;m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
assert m.due({"interval_seconds":30},100)["due"] is False
assert m.due({"interval_seconds":60,"last_completed_epoch":None},100)["due"] is True
assert m.due({"interval_seconds":60,"last_completed_epoch":100},159)["due"] is False
assert m.due({"interval_seconds":60,"last_completed_epoch":100},160)["due"] is True
assert m.due({"interval_seconds":60,"last_completed_epoch":200},100)["reason"]=="clock_regression"
assert m.due({"interval_seconds":60},100)["execution_authorized"] is False
print("AO-4 bounded scheduler contract: GREEN")

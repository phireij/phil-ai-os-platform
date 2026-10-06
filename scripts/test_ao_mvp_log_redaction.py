#!/usr/bin/env python3
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/"scripts/ao_mvp_log_redaction.py";s=importlib.util.spec_from_file_location("x",p);assert s and s.loader;m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
r=m.sanitize({"work_id":"x","authorization":"Bearer abc","customer_email":"a@b.test","message":"ok"})
assert r["work_id"]=="x" and r["message"]=="ok"
assert r["authorization"]=="[REDACTED]" and r["customer_email"]=="[REDACTED]"
print("AO-MVP runtime log redaction contract: GREEN")

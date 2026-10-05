#!/usr/bin/env python3
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"scripts/validate_ao_mvp_hosted_runtime_activation.py"
s=importlib.util.spec_from_file_location("x",p);assert s and s.loader
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
t=json.loads((ROOT/"ops/runtime/ao-mvp-hosted-runtime-activation-evidence.template.json").read_text())
r=m.validate(t);assert r["ready"] is False and r["activation_authorized"] is False
t["target"]={"provider":"fixture","runtime":"fixture","owner":"fixture"}
t["revision"]={"git_sha":"abc","package_digest":"digest","contract_ci":"success","supply_chain_ci":"success"}
t["checks"]={k:True for k in m.REQUIRED}
t["approval"]={"explicit":True,"scope":"hosted A1 only","evidence_ref":"fixture"}
t["prohibited_scope_unchanged"]=True
r=m.validate(t);assert r["ready"] is True and r["activation_authorized"] is False
print("AO-MVP hosted runtime activation validator: GREEN")

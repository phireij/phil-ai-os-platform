#!/usr/bin/env python3
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"scripts/ao_mvp_runtime_rollback_drill.py"
r=subprocess.run([sys.executable,str(p),"--revision","fixture-revision"],cwd=ROOT,capture_output=True,text=True,check=True)
out=json.loads(r.stdout)
assert out=={"authority_effect":"reduce_only","dispatch_enabled":False,"effective_autonomy":"A0","evidence_preserved":True,"prior_revision":"fixture-revision","production_mutation_authorized":False,"service_state":"stopped"}
print("AO-MVP rollback drill observability: GREEN")

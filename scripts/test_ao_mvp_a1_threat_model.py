#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def loadmod(name,path):
 s=importlib.util.spec_from_file_location(name,path); assert s and s.loader
 m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
D=loadmod("d",ROOT/"scripts/ao_mvp_a1_dispatcher_simulation.py")
R=loadmod("r",ROOT/"scripts/ao_mvp_a1_rollback.py")
matrix=json.loads((ROOT/"ops/authorizations/a1-authority-matrix.v1.json").read_text())
ledger=D.DispatchLedger()
safe={"work_id":"x","capability":"tests_static_analysis","production":False,"mutation":False}
a=ledger.decide(safe,matrix)
assert a["decision"]=="allow_simulation" and a["execution_performed"] is False
assert ledger.decide(safe,matrix)["reason"]=="replay"
for cap in ["pull_request_merge","production_publish_or_cutover","payment_or_refund_execution","live_customer_messaging","authority_matrix_self_widening","unknown_capability"]:
 r=ledger.decide({"work_id":cap,"capability":cap,"production":False,"mutation":False},matrix)
 assert r["decision"]=="deny"
for key,val in [("production",True),("mutation",True)]:
 q={"work_id":key,"capability":"documentation","production":False,"mutation":False}; q[key]=val
 assert ledger.decide(q,matrix)["decision"]=="deny"
rb=R.rollback({**matrix,"activation_state":"active","effective_autonomy_ceiling":"A1","automatic_execution_enabled":True})
assert rb["effective_autonomy_ceiling"]=="A0"
assert rb["automatic_execution_enabled"] is False
assert rb["production_mutation_authorized"] is False
assert rb["rollback"]["production_mutation"] is False
print("AO-MVP A1 dispatcher/rollback threat-model tests: GREEN")

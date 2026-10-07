#!/usr/bin/env python3
"""Synthetic hosted-runtime rollback acceptance: stop + effective A0, preserve evidence."""
from __future__ import annotations
import argparse,json
def rollback(runtime:dict)->dict:
 return {"service_state":"stopped","effective_autonomy":"A0","dispatch_enabled":False,"production_mutation_authorized":False,"evidence_preserved":True,"authority_effect":"reduce_only","prior_revision":runtime.get("revision")}

if __name__=="__main__":
 parser=argparse.ArgumentParser(description="Emit the bounded AO-MVP rollback proof")
 parser.add_argument("--revision",default=None)
 args=parser.parse_args()
 print(json.dumps(rollback({"revision":args.revision}),sort_keys=True))

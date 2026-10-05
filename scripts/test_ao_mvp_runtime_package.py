#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];m=json.loads((ROOT/"ops/runtime/ao-mvp-hosted-runtime-package.v1.json").read_text())
assert m["status"]=="inert_not_deployed"
assert m["network_egress"]=="none_by_default"
assert m["production_credentials_required"] is False
assert m["authority"]["deployment_authorized"] is False
assert m["authority"]["production_mutation_authorized"] is False
assert m["rollback"]["delete_evidence"] is False
print("AO-MVP inert hosted-runtime package contract: GREEN")

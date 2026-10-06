#!/usr/bin/env python3
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; p=ROOT/"scripts/ao_mvp_ruby_readiness_adapter.py"
s=importlib.util.spec_from_file_location("r",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m); o=m.build()
assert o["project_id"]=="rubys-cake-delights-hq"
assert o["facts"]["production_activation_ready"] is False
assert o["facts"]["customer_order_creation_authorized"] is False
assert o["facts"]["inventory_mutation_authorized"] is False
assert o["facts"]["automatic_production_execution_authorized"] is False
assert o["freshness"]=="stale"
assert len(o["facts"]["unmet_readiness_controls"])>=1
print("Ruby AO read-only readiness adapter: GREEN")

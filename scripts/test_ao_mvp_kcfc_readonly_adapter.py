#!/usr/bin/env python3
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; p=ROOT/"scripts/ao_mvp_kcfc_readonly_adapter.py"
s=importlib.util.spec_from_file_location("k",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m); o=m.build()
assert o["facts"]["repository"]=="phireij/KCFC-Portal"
assert o["facts"]["integration_mode"]=="read_only"
assert o["facts"]["production_mutation_authorized"] is False
assert o["authority"]=={"authority_effect":"none","mutation_authorized":False}
print("KCFC AO read-only repository adapter: GREEN")

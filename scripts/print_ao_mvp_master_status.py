#!/usr/bin/env python3
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; p=ROOT/"scripts/ao_mvp_generate_master_status.py"
s=importlib.util.spec_from_file_location("g",p); assert s and s.loader
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
print(json.dumps(m.build(),indent=2,sort_keys=True))

#!/usr/bin/env python3
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"ops/runtime/hostinger/compose.inert.yml";s=p.read_text()
for x in ("UNBUILT","network_mode: none","read_only: true","restart: unless-stopped","PHIL_AI_OS_PRODUCTION_MUTATION: \"false\"","PHIL_AI_OS_PROVIDER_EXECUTION: \"false\"","/var/lib/phil-ai-os/ao-mvp"):
 assert x in s,x
assert "ports:" not in s
print("AO-MVP inert Hostinger compose fixture: GREEN")

#!/usr/bin/env python3
import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"ops/runtime/ao-mvp-public-webhook-nonapplying-ingress-plan.v1.json"
def validate(d):
 e=[]
 if d.get("status")!="planned_not_applied" or d.get("apply_changes") is not False: e.append("plan must remain non-applying")
 if d.get("authority_effect")!="none" or d.get("public_webhook_activation_authorized") is not False: e.append("plan cannot grant authority")
 i=d.get("dedicated_ingress_identity",{})
 if i.get("hostname") is not None: e.append("real hostname must remain unset before approval")
 for k in ("must_not_reuse_hermes","must_not_reuse_existing_traefik","must_not_reuse_phil_ai_os_core"):
  if i.get(k) is not True: e.append(k+" required")
 dns=d.get("dns",{})
 if dns.get("reviewed_not_applied") is not True: e.append("DNS plan review marker required")
 for k in ("record_type","record_name","target","ttl"):
  if dns.get(k) is not None: e.append("DNS concrete values must remain unset")
 rp=d.get("route_and_port",{})
 if rp.get("reviewed_not_applied") is not True or rp.get("dedicated_route_required") is not True: e.append("dedicated route plan required")
 if rp.get("public_port") is not None or rp.get("existing_route_reuse") is not False or rp.get("existing_public_port_change") is not False: e.append("route/port must remain inert")
 tls=d.get("tls",{})
 if tls.get("plan_defined") is not True or tls.get("hostname_binding") is not None or tls.get("plaintext_fallback") is not False: e.append("TLS plan must be defined but unbound")
 cd=d.get("credentials_and_data",{})
 if any(cd.get(k) is not False for k in ("production_credentials","production_data","twilio","customer_systems","payments")): e.append("production/customer capability forbidden")
 return e
def main():
 d=json.loads(P.read_text()); e=validate(d)
 if e: print("\n".join("FAIL: "+x for x in e)); raise SystemExit(1)
 print("PASS: ingress/DNS/route/TLS plan is reviewed, isolated and non-applying")
if __name__=="__main__": main()

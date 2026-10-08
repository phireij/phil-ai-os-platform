#!/usr/bin/env python3
import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"ops/runtime/ao-mvp-public-webhook-activation-manifest.v1.json"
def validate(d):
 e=[]
 if d.get("status")!="prepared_not_authorized":e.append("status must remain prepared_not_authorized")
 if d.get("authority_effect")!="none":e.append("authority effect must be none")
 if d.get("production_mutation_authorized") is not False:e.append("production mutation forbidden")
 if d.get("public_webhook_activation_authorized") is not False:e.append("activation must remain unauthorized")
 s=d.get("source",{})
 if not s.get("verified_repository_head") or s.get("verified_ci") is not True:e.append("verified repository source required")
 i=d.get("ingress",{})
 if i.get("identity")!="ao-mvp-public-webhook":e.append("dedicated identity required")
 if i.get("hostname") is not None or i.get("public_port") is not None:e.append("network values must remain unset before approval")
 for k in ("reuse_hermes_hostname","reuse_existing_traefik_route","reuse_phil_ai_os_core_workload"):
  if i.get(k) is not False:e.append(k+" forbidden")
 if len(d.get("isolation_acceptance",[]))<6:e.append("isolation acceptance incomplete")
 if len(d.get("post_approval_sequence",[]))<10:e.append("post-approval sequence incomplete")
 if d.get("rollback")!=["disable ingress","remove dedicated route","close dedicated public port if one was introduced","preserve private A1 runtime","preserve evidence"]:e.append("rollback sequence invalid")
 return e
def main():
 d=json.loads(P.read_text());e=validate(d)
 if e:print("\n".join("FAIL: "+x for x in e));raise SystemExit(1)
 print("PASS: public webhook activation manifest is complete and non-authorizing")
if __name__=="__main__":main()

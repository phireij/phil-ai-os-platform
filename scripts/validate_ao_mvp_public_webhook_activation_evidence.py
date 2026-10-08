#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=ROOT/"ops/runtime/ao-mvp-public-webhook-activation-evidence.template.json"
REQUIRED_EVIDENCE=(
 "exact_revision_ci_green","supply_chain_ci_green","authentication_contract_green",
 "replay_protection_green","payload_validation_green","rate_limit_abuse_green",
 "log_redaction_green","hermes_isolation_green","zero_production_mutation_green",
 "rollback_green","synthetic_canary_green","tls_green",
)

def validate_template(d):
 errors=[]
 if d.get("schema")!="phil-ai-os-public-webhook-activation-evidence": errors.append("bad schema")
 if d.get("status")!="template_not_authorized": errors.append("template must remain non-authorizing")
 if d.get("public_webhook_activation_authorized") is not False: errors.append("public activation must be false")
 if d.get("production_mutation_authorized") is not False: errors.append("production mutation must be false")
 if d.get("authority_effect")!="none": errors.append("authority effect must be none")
 if d.get("dedicated_hostname") is not None: errors.append("template cannot preselect hostname")
 for k in ("hermes_reuse","existing_traefik_reuse","existing_core_workload_reuse","production_credentials_present","production_data_present","twilio_enabled","customer_systems_enabled","payments_enabled"):
  if d.get(k) is not False: errors.append(k+" must be false")
 ev=d.get("evidence",{})
 missing=[k for k in REQUIRED_EVIDENCE if k not in ev]
 if missing: errors.append("missing evidence: "+",".join(missing))
 if any(ev.get(k) is not False for k in REQUIRED_EVIDENCE): errors.append("template evidence must start false")
 ap=d.get("approval",{})
 if ap.get("phase")!="public_webhook_activation": errors.append("wrong approval phase")
 if ap.get("ceo_explicit_approval") is not False: errors.append("CEO approval must start false")
 if ap.get("approved_at") is not None or ap.get("scope") is not None: errors.append("approval metadata must start empty")
 return errors

def main():
 d=json.loads(TEMPLATE.read_text())
 errors=validate_template(d)
 if errors:
  print("\n".join("FAIL: "+e for e in errors)); raise SystemExit(1)
 print("PASS: public webhook activation evidence template is non-authorizing")
if __name__=="__main__": main()

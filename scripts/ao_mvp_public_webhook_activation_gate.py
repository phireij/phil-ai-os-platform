#!/usr/bin/env python3
"""Pure activation decision gate. No side effects."""

REQUIRED=(
 "exact_revision_ci_green","supply_chain_ci_green","authentication_contract_green",
 "replay_protection_green","payload_validation_green","rate_limit_abuse_green",
 "log_redaction_green","hermes_isolation_green","zero_production_mutation_green",
 "rollback_green","synthetic_canary_green","tls_green",
)

def decide(evidence: dict):
 reasons=[]
 if evidence.get("public_webhook_activation_authorized") is not True:
  reasons.append("phase-specific public webhook approval absent")
 if evidence.get("production_mutation_authorized") is not False:
  reasons.append("production mutation boundary violated")
 if evidence.get("authority_effect")!="none":
  reasons.append("authority effect boundary violated")
 host=evidence.get("dedicated_hostname")
 if not isinstance(host,str) or not host.strip():
  reasons.append("dedicated hostname evidence absent")
 elif "hermes" in host.lower():
  reasons.append("Hermes hostname reuse forbidden")
 for k in ("hermes_reuse","existing_traefik_reuse","existing_core_workload_reuse","production_credentials_present","production_data_present","twilio_enabled","customer_systems_enabled","payments_enabled"):
  if evidence.get(k) is not False: reasons.append(k+" must remain false")
 ev=evidence.get("evidence",{})
 for k in REQUIRED:
  if ev.get(k) is not True: reasons.append(k+" not green")
 ap=evidence.get("approval",{})
 if ap.get("phase")!="public_webhook_activation" or ap.get("ceo_explicit_approval") is not True:
  reasons.append("explicit CEO phase approval missing")
 if not ap.get("approved_at") or not ap.get("scope"):
  reasons.append("approval metadata incomplete")
 return {"ready":not reasons,"reasons":reasons,"authority_effect":"none"}

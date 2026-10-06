#!/usr/bin/env python3
REQUIRED=("persistent_volume_restart","concurrent_single_worker","crash_recovery_no_duplicate","corrupt_state_fail_closed","health_fail_closed","log_redaction","egress_policy","a1_denylist_end_to_end","rollback_drill","no_production_credentials")
def validate(e):
 missing=[]
 for k in ("provider","runtime","owner"):
  if not e.get("target",{}).get(k): missing.append("target."+k)
 for k in ("git_sha","package_digest"):
  if not e.get("revision",{}).get(k): missing.append("revision."+k)
 for k in ("contract_ci","supply_chain_ci"):
  if e.get("revision",{}).get(k)!="success": missing.append("revision."+k)
 for k in REQUIRED:
  if e.get("checks",{}).get(k) is not True: missing.append("checks."+k)
 if e.get("approval",{}).get("explicit") is not True: missing.append("approval.explicit")
 if not e.get("approval",{}).get("scope"): missing.append("approval.scope")
 if e.get("prohibited_scope_unchanged") is not True: missing.append("prohibited_scope_unchanged")
 return {"ready":not missing,"missing":missing,"activation_authorized":False,"authority_effect":"none"}

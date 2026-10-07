#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "ops/runtime/ao-mvp-public-webhook-readiness.v1.json"

DENIED_TRUE = (
    "public_webhook_activation_authorized",
    "production_mutation_authorized",
    "hermes_reuse_authorized",
    "dns_change_authorized",
    "public_route_change_authorized",
    "public_port_change_authorized",
    "production_credentials_authorized",
    "production_data_authorized",
    "twilio_authorized",
    "customer_systems_authorized",
    "payments_authorized",
)

REQUIRED_CHECKS = (
    "dedicated_ingress_identity",
    "hermes_isolation_proven",
    "dns_plan_reviewed_not_applied",
    "route_port_plan_reviewed_not_applied",
    "tls_plan_defined",
    "authentication_contract_green",
    "replay_protection_green",
    "payload_validation_green",
    "rate_limit_abuse_green",
    "log_redaction_green",
    "zero_production_mutation_capability_green",
    "synthetic_e2e_green",
    "rollback_plan_green",
    "exact_revision_ci_green",
    "phase_specific_ceo_approval_recorded",
)

def validate(data):
    errors = []
    if data.get("schema") != "phil-ai-os-public-webhook-activation-readiness":
        errors.append("unexpected schema")
    if data.get("authority_effect") != "none":
        errors.append("authority_effect must remain none")
    if data.get("private_a1_checkpoint_complete") is not True:
        errors.append("private A1 predecessor checkpoint must be explicit")
    for key in DENIED_TRUE:
        if data.get(key) is not False:
            errors.append(f"{key} must be false before separate activation approval")
    checks = data.get("checks")
    if not isinstance(checks, dict):
        errors.append("checks must be an object")
        return errors
    missing = [key for key in REQUIRED_CHECKS if key not in checks]
    if missing:
        errors.append("missing checks: " + ", ".join(missing))
    # Planning record is intentionally NOT READY. No individual readiness check
    # may silently grant authority; phase-specific approval remains separate.
    if data.get("status") != "planning_only_not_authorized":
        errors.append("planning record status must remain planning_only_not_authorized")
    return errors

def main():
    data = json.loads(RECORD.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        raise SystemExit(1)
    print("PASS: public-webhook planning record is fail-closed and non-authorizing")

if __name__ == "__main__":
    main()

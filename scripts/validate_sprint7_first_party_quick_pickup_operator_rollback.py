#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "ops/readiness/ruby-first-party-quick-pickup-operator-rollback-evidence.template.json"
READINESS = ROOT / "ops/readiness/ruby-first-party-quick-pickup-readiness.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_QUICK_PICKUP_OPERATOR_ROLLBACK_EVIDENCE_FAILED: {message}")


def main() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))

    require(evidence.get("version") == "ruby-first-party-quick-pickup-operator-rollback-evidence-v1", "schema drift")
    require(evidence.get("environment") == "preproduction", "evidence must remain preproduction-scoped")
    require(evidence.get("synthetic_only") is True, "evidence must remain synthetic-only")
    require(evidence.get("evidence_status") == "PENDING", "template cannot claim accepted evidence")

    for key in (
        "no_order_created",
        "no_payment_executed",
        "no_inventory_mutation",
        "no_capacity_mutation",
        "no_production_publish",
    ):
        require(evidence.get(key) is True, f"safety invariant missing: {key}")

    operator = evidence.get("operator_acceptance")
    rollback = evidence.get("rollback_disable_acceptance")
    require(isinstance(operator, dict), "operator acceptance block missing")
    require(isinstance(rollback, dict), "rollback acceptance block missing")
    for key, value in operator.items():
        require(value is False, f"template must not pre-accept operator evidence: {key}")
    for key, value in rollback.items():
        require(value is False, f"template must not pre-accept rollback evidence: {key}")

    authority = evidence.get("authority")
    require(isinstance(authority, dict), "authority block missing")
    for key, value in authority.items():
        require(value is False, f"operator evidence template expanded authority: {key}")

    production = readiness.get("production_readiness")
    require(isinstance(production, dict), "Quick Pickup production readiness missing")
    require(production.get("controlled_handset_and_operator_acceptance_green") is False, "operator acceptance cannot become GREEN from template preparation")
    require(production.get("rollback_disable_path_green") is False, "rollback acceptance cannot become GREEN from template preparation")
    require(production.get("production_activation_ready") is False, "production activation must remain false")

    preparation = readiness.get("bounded_engineering_preparation")
    require(isinstance(preparation, dict), "bounded engineering preparation missing")
    require(preparation.get("operator_rollback_acceptance_harness_prepared") is True, "operator/rollback acceptance harness not recorded")
    require(preparation.get("operator_disable_control_production_accepted") is False, "disable control cannot be production-accepted without evidence")

    print("PHIL_AI_OS_QUICK_PICKUP_OPERATOR_ROLLBACK_EVIDENCE_GREEN harness=prepared evidence=pending operator_acceptance=false rollback_acceptance=false authority=false")


if __name__ == "__main__":
    main()

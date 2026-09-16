#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "ops/readiness/ruby-first-party-quick-pickup-readiness.json"
ROADMAP = ROOT / "docs/MASTER_EXECUTIVE_ROADMAP_SCHEDULE_CONTROL.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_FIRST_PARTY_QUICK_PICKUP_READINESS_FAILED: {message}")


def main() -> None:
    data = json.loads(READINESS.read_text(encoding="utf-8"))
    roadmap = ROADMAP.read_text(encoding="utf-8")
    require(data.get("version") == "ruby-first-party-quick-pickup-readiness-v1", "schema drift")
    require(data.get("air_mobile_order_required_for_v1") is False, "Air Mobile remains a V1 dependency")
    inventory = data.get("airregi_inventory")
    require(isinstance(inventory, dict), "AirREGI posture missing")
    require(inventory.get("api_verified") is False, "unverified AirREGI API cannot become a production assumption")
    require(inventory.get("csv_fallback_documented") is True, "CSV fallback record missing")
    require(inventory.get("authority") == "not_assumed", "AirREGI authority drift")
    scope = data.get("ceo_scope_authorization")
    require(isinstance(scope, dict) and scope.get("controlled_production_activation_authorized") is True, "CEO controlled-activation scope missing")
    require(scope.get("overrides_readiness") is False and scope.get("automatic_execution_authorized") is False, "scope authorization expanded")

    preparation = data.get("bounded_engineering_preparation")
    require(isinstance(preparation, dict), "bounded Quick Pickup engineering preparation missing")
    for key in (
        "fixture_inventory_decision_prepared",
        "fixture_capacity_and_cutoff_decision_prepared",
        "fixture_combined_decision_preview_prepared",
        "fixture_operator_disable_control_prepared",
    ):
        require(preparation.get(key) is True, f"bounded Quick Pickup preparation regressed: {key}")
    require(preparation.get("operator_disable_control_production_accepted") is False, "fixture disable control cannot satisfy production acceptance")
    require(preparation.get("production_readiness_effect") == "none", "bounded engineering preparation changed production readiness")

    readiness = data.get("production_readiness")
    require(isinstance(readiness, dict), "production readiness missing")
    for key, value in readiness.items():
        require(value is False, f"unverified quick-pickup readiness unexpectedly green: {key}")
    authority = data.get("authority")
    require(isinstance(authority, dict), "authority posture missing")
    for key, value in authority.items():
        require(value is False, f"quick-pickup authority expanded: {key}")
    require("first-party Quick Pickup" in roadmap, "roadmap first-party Quick Pickup reconciliation missing")
    require("Air Mobile Quick Pickup production URL" not in roadmap, "roadmap retains Air Mobile launch dependency")
    print("PHIL_AI_OS_FIRST_PARTY_QUICK_PICKUP_READINESS_GREEN air_mobile_v1=false production_ready=false rollback_foundation=prepared_not_accepted authority=false")


if __name__ == "__main__":
    main()

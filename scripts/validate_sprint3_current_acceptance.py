#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "ops" / "readiness" / "ruby-sprint3-current-acceptance-2026-09-03.json"
ROADMAP = ROOT / "docs" / "MASTER_EXECUTIVE_ROADMAP_SCHEDULE_CONTROL.md"
CHECKPOINT = ROOT / "docs" / "SPRINT_3_CURRENT_ACCEPTANCE_CHECKPOINT_2026-09-03.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_SPRINT_3_CURRENT_ACCEPTANCE_FAILED: {message}")


def main() -> int:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    roadmap = ROADMAP.read_text(encoding="utf-8")
    checkpoint = CHECKPOINT.read_text(encoding="utf-8")

    executive = record["executive_roadmap"]
    require(executive["current_primary_sprint"] == 3, "Sprint 3 must remain current primary sprint")
    require(executive["sprint4_parallel_acceleration"] is True, "Sprint 4 parallel acceleration should remain recorded")
    require(executive["formal_sprint4_entry"] is False, "formal Sprint 4 entry must remain false before Sprint 3 closure")

    technical = record["technical_acceptance"]
    for key in (
        "woocommerce_foundation_green",
        "isolated_wordpress_woocommerce_runtime_green",
        "preproduction_configuration_green",
        "production_read_only_identity_green",
        "catalog_tax_intake_fail_closed_green",
        "catalog_provenance_integrity_guard_green",
        "catalog_dry_run_reconciliation_ready",
    ):
        require(technical[key] is True, f"technical acceptance regressed: {key}")
    require(technical["production_mutation_enabled"] is False, "production mutation must remain disabled")

    remaining = record["remaining_sprint3_exit_inputs"]
    require(remaining["final_owner_approved_catalog"] is False, "checkpoint must not invent final catalog completion")
    require(remaining["japan_tax_evidence_and_decision"] is False, "checkpoint must not invent tax completion")

    exit_state = record["exit_state"]
    for key in (
        "sprint3_exit_inputs_complete",
        "formal_sprint3_closure",
        "production_catalog_write_ready",
        "tax_activation_ready",
    ):
        require(exit_state[key] is False, f"exit gate must remain fail-closed: {key}")

    authority = record["authority"]
    require(authority["mutation_authorized"] is False, "mutation authority must remain false")
    require(authority["production_publish_authorized"] is False, "publish authority must remain false")
    require(authority["automatic_production_execution"] is False, "automatic production execution must remain false")

    require("Sprint 3 — WooCommerce Foundation is the CURRENT PRIMARY SPRINT" in roadmap, "master roadmap Sprint 3 position missing")
    require("PHIL_AI_OS_SPRINT_3_CURRENT_PRIMARY_PENDING_OWNER_INPUTS" in checkpoint, "checkpoint marker missing")

    print("PHIL_AI_OS_SPRINT_3_CURRENT_ACCEPTANCE_GREEN status=pending_owner_inputs mutation_authorized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

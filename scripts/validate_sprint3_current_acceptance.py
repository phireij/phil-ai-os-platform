#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "ops" / "readiness" / "ruby-sprint3-current-acceptance-2026-09-03.json"
ROADMAP = ROOT / "docs" / "MASTER_EXECUTIVE_ROADMAP_SCHEDULE_CONTROL.md"
CHECKPOINT = ROOT / "docs" / "SPRINT_3_CURRENT_ACCEPTANCE_CHECKPOINT_2026-09-03.md"
TAX = ROOT / "ops" / "readiness" / "ruby-japan-consumption-tax-status-2026-09-03.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_SPRINT_3_CURRENT_ACCEPTANCE_FAILED: {message}")


def main() -> int:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    tax = json.loads(TAX.read_text(encoding="utf-8"))
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
        "production_read_only_connectivity_green",
        "catalog_tax_intake_fail_closed_green",
        "catalog_provenance_integrity_guard_green",
        "catalog_dry_run_reconciliation_ready",
        "japan_tax_decision_green",
    ):
        require(technical[key] is True, f"technical acceptance regressed: {key}")
    require(technical["woocommerce_tax_route"] == "disabled", "exempt-business tax route drift")
    require(technical["production_mutation_enabled"] is False, "production mutation must remain disabled")

    require(tax["decision"]["consumption_tax_status"] == "exempt", "tax status drift")
    require(tax["decision"]["qualified_invoice_status"] == "not_registered", "invoice status drift")
    require(tax["decision"]["woocommerce_tax_implementation_route"] == "tax_disabled_candidate", "tax route drift")
    require(tax["decision"]["tax_decision_ready"] is True, "tax decision must remain GREEN")
    for key in ("tax_write_ready", "tax_activation_authorized", "mutation_authorized", "production_publish_authorized"):
        require(tax["authority"][key] is False, f"tax evidence must remain non-authorizing: {key}")

    remaining = record["remaining_sprint3_exit_inputs"]
    require(remaining["final_owner_approved_catalog"] is False, "checkpoint must not invent final catalog completion")
    require(remaining["japan_tax_evidence_and_decision"] is True, "tax evidence/decision should be GREEN")

    exit_state = record["exit_state"]
    require(exit_state["sprint3_exit_inputs_complete"] is False, "Sprint 3 cannot close before final catalog")
    require(exit_state["formal_sprint3_closure"] is False, "formal Sprint 3 closure must remain false")
    require(exit_state["production_catalog_write_ready"] is False, "catalog write must remain fail-closed")
    require(exit_state["tax_decision_ready"] is True, "tax decision should remain ready")
    require(exit_state["tax_activation_required"] is False, "tax activation must not be required for exempt route")
    require(exit_state["tax_activation_ready"] is False, "tax activation must remain false")

    authority = record["authority"]
    require(authority["mutation_authorized"] is False, "mutation authority must remain false")
    require(authority["production_publish_authorized"] is False, "publish authority must remain false")
    require(authority["automatic_production_execution"] is False, "automatic production execution must remain false")

    sprint3_position_markers = (
        "Sprint 3 — WooCommerce Foundation is the CURRENT PRIMARY SPRINT",
        "Sprint 3 — WooCommerce Foundation remains the CURRENT PRIMARY SPRINT",
    )
    require(
        any(marker in roadmap for marker in sprint3_position_markers),
        "master roadmap Sprint 3 position missing",
    )
    require("PHIL_AI_OS_SPRINT_3_CURRENT_PRIMARY_PENDING_FINAL_CATALOG_ONLY" in checkpoint, "checkpoint marker missing")

    print("PHIL_AI_OS_SPRINT_3_CURRENT_ACCEPTANCE_GREEN status=pending_final_catalog_only tax_decision=green mutation_authorized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

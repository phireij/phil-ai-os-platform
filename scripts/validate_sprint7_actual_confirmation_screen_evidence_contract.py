#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/cx/final-confirmation-screen-evidence.schema.json"
TEMPLATE = ROOT / "ops/readiness/ruby-actual-woocommerce-final-confirmation-screen-evidence.template.json"
PLAN = ROOT / "docs/RUBY_ACTUAL_WOOCOMMERCE_FINAL_SCREEN_EVIDENCE_CAPTURE_PLAN_2026-09-04.md"
CANDIDATE = ROOT / "ops/readiness/ruby-tokushoho-publication-candidate-2026-09-04.json"
ISOLATED = ROOT / "ops/readiness/ruby-isolated-final-confirmation-preview-2026-09-04.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_ACTUAL_CONFIRMATION_SCREEN_EVIDENCE_CONTRACT_FAILED: {message}")


def nested_const(schema: dict, *path: str):
    node = schema
    for key in path:
        node = node[key]
    return node["const"]


def main() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    isolated = json.loads(ISOLATED.read_text(encoding="utf-8"))

    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "schema draft drift")
    require(schema.get("additionalProperties") is False, "evidence schema must reject unknown top-level fields")
    required = set(schema.get("required", []))
    for field in (
        "environment",
        "synthetic_customer_data_only",
        "contains_personal_data",
        "contains_secret_material",
        "screen_capture_refs",
        "observations",
        "authority",
        "evidence_complete",
        "actual_final_confirmation_screen_reviewed",
    ):
        require(field in required, f"schema required field missing: {field}")

    require(nested_const(schema, "properties", "version") == "ruby-woocommerce-final-confirmation-screen-evidence-v1", "schema version drift")
    require(nested_const(schema, "properties", "environment") == "preproduction", "screen evidence must remain preproduction-only")
    require(nested_const(schema, "properties", "source_url_class") == "sanitized_preproduction_checkout", "source URL class drift")
    require(nested_const(schema, "properties", "contains_personal_data") is False, "schema must forbid personal data")
    require(nested_const(schema, "properties", "contains_secret_material") is False, "schema must forbid secret material")
    require(nested_const(schema, "properties", "observations", "properties", "final_action_not_invoked") is True, "schema must require final action not invoked")
    for key in (
        "order_creation_authorized",
        "payment_execution_authorized",
        "production_publish_authorized",
        "catalog_mutation_authorized",
        "dns_cutover_authorized",
    ):
        require(nested_const(schema, "properties", "authority", "properties", key) is False, f"schema authority expanded: {key}")

    require(template.get("version") == "ruby-woocommerce-final-confirmation-screen-evidence-v1", "template version drift")
    require(template.get("environment") == "preproduction", "template must remain preproduction-only")
    require(template.get("source_url_class") == "sanitized_preproduction_checkout", "template source class drift")
    require(template.get("synthetic_customer_data_only") is True, "template must use synthetic customer data only")
    require(template.get("contains_personal_data") is False, "template contains personal data")
    require(template.get("contains_secret_material") is False, "template contains secret material")
    require(template.get("screen_capture_refs") == [], "pending template must not claim screen artifacts")
    require(template.get("captured_at") is None, "pending template cannot claim capture time")
    require(template.get("evidence_complete") is False, "pending evidence template cannot be complete")
    require(template.get("actual_final_confirmation_screen_reviewed") is False, "pending template cannot claim actual-screen review")
    require(template["observations"]["final_action_not_invoked"] is True, "final action safeguard drift")
    for key, value in template["authority"].items():
        require(value is False, f"template authority expanded unexpectedly: {key}")
    for key, value in template["observations"].items():
        if key != "final_action_not_invoked":
            require(value is False, f"pending template cannot pre-claim observation: {key}")

    screen = candidate["confirmation_screen"]
    require(screen["actual_screen_evidence_contract_ready"] is True, "candidate lost evidence-contract readiness")
    require(screen["actual_screen_evidence_schema_ref"] == "contracts/cx/final-confirmation-screen-evidence.schema.json", "candidate schema ref drift")
    require(screen["actual_screen_evidence_template_ref"] == "ops/readiness/ruby-actual-woocommerce-final-confirmation-screen-evidence.template.json", "candidate template ref drift")
    require(screen["actual_screen_capture_plan_ref"] == "docs/RUBY_ACTUAL_WOOCOMMERCE_FINAL_SCREEN_EVIDENCE_CAPTURE_PLAN_2026-09-04.md", "candidate capture-plan ref drift")
    require(screen["actual_final_screen_reviewed"] is False, "contract readiness cannot close actual-screen gate")
    require(screen["actual_final_screen_evidence_captured"] is False, "contract readiness cannot claim captured evidence")
    require(screen["real_order_required_for_review"] is False, "real order must not be required")
    require(screen["real_payment_required_for_review"] is False, "real payment must not be required")
    for key, value in candidate["authority"].items():
        require(value is False, f"candidate authority expanded unexpectedly: {key}")

    actual = isolated["actual_woocommerce_screen"]
    require(actual["reviewed"] is False and actual["evidence_captured"] is False, "isolated milestone cannot claim actual screen evidence")
    require(actual["satisfied_by_isolated_preview"] is False, "isolated preview cannot satisfy actual screen gate")

    plan = PLAN.read_text(encoding="utf-8")
    for phrase in (
        "ACTUAL SCREEN REVIEW PENDING",
        "preproduction only",
        "Do not click",
        "synthetic QA customer details only",
        "evidence_complete: false",
        "actual_final_confirmation_screen_reviewed: false",
        "payment_execution_authorized: false",
        "PHIL_AI_OS_RUBY_ACTUAL_WOOCOMMERCE_FINAL_SCREEN_EVIDENCE_CONTRACT_READY_REVIEW_PENDING_FAIL_CLOSED",
    ):
        require(phrase in plan, f"capture plan safeguard missing: {phrase}")

    print("PHIL_AI_OS_RUBY_ACTUAL_WOOCOMMERCE_FINAL_SCREEN_EVIDENCE_CONTRACT_GREEN preproduction=true pii=false secrets=false")
    print("PHIL_AI_OS_RUBY_ACTUAL_WOOCOMMERCE_FINAL_SCREEN_REVIEW_PENDING_FAIL_CLOSED order_creation=false payment_execution=false")


if __name__ == "__main__":
    main()

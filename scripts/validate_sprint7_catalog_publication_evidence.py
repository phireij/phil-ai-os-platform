#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/commerce/ruby-catalog-publication-evidence.schema.json"
TEMPLATE = ROOT / "ops/readiness/ruby-catalog-publication-evidence.template.json"
DECISION = ROOT / "ops/readiness/ruby-initial-launch-catalog-v1-ceo-decision-2026-09-16.json"
GO_NO_GO = ROOT / "ops/readiness/ruby-final-go-no-go-gate-2026-09-02.json"

CHECK_KEYS = (
    "final_bilingual_customer_facing_copy_confirmed",
    "verified_product_media_references_confirmed",
    "final_fulfillment_package_shipping_classifications_confirmed",
    "subsystem_preflight_green",
    "controlled_publication_acceptance_green",
)
AUTHORITY_KEYS = (
    "woocommerce_catalog_write_authorized",
    "production_publish_authorized",
    "payment_execution_authorized",
    "automatic_production_execution_authorized",
)
PRODUCTS = {
    "Moist Chocolate Round Cake",
    "Fudgy Milky Bar",
    "Cheezy Ensaymada",
}
PENDING = "PENDING_CATALOG_PUBLICATION_CONTENT_FAIL_CLOSED"
GREEN = "CATALOG_PUBLICATION_ACCEPTANCE_GREEN"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_CATALOG_PUBLICATION_EVIDENCE_FAILED: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_evidence(data: dict, *, expect_pending: bool | None = None) -> None:
    require(data.get("version") == "ruby-catalog-publication-evidence-v1", "evidence version drift")
    require(data.get("scope_ref") == "ops/readiness/ruby-initial-launch-catalog-v1-ceo-decision-2026-09-16.json", "scope ref drift")
    require(data.get("source_ref") == "commerce/woocommerce/fixtures/working-catalog-subset-2026-09-11.json", "source ref drift")
    products = data.get("products")
    require(isinstance(products, list) and set(products) == PRODUCTS and len(products) == 3, "approved product scope drift")
    require(data.get("contains_secret_material") is False, "secret material must not be retained")

    checks = data.get("checks")
    require(isinstance(checks, dict), "checks object missing")
    require(set(checks) == set(CHECK_KEYS), "catalog publication check set drift")
    require(all(isinstance(checks[key], bool) for key in CHECK_KEYS), "catalog publication checks must be boolean")

    authority = data.get("authority")
    require(isinstance(authority, dict), "authority object missing")
    require(set(authority) == set(AUTHORITY_KEYS), "authority field set drift")
    for key in AUTHORITY_KEYS:
        require(authority[key] is False, f"authority expanded: {key}")

    refs = data.get("evidence_refs")
    require(isinstance(refs, list), "evidence_refs must be a list")
    require(all(isinstance(item, str) and item for item in refs), "evidence_refs must contain non-empty strings")
    require(len(refs) == len(set(refs)), "evidence_refs must be unique")

    evidence_complete = data.get("evidence_complete")
    acceptance_green = data.get("acceptance_green")
    require(isinstance(evidence_complete, bool), "evidence_complete must be boolean")
    require(isinstance(acceptance_green, bool), "acceptance_green must be boolean")

    green_prerequisites = all(checks[key] is True for key in CHECK_KEYS) and len(refs) > 0
    if acceptance_green:
        require(green_prerequisites, "GREEN catalog acceptance requires every publication prerequisite and evidence")
        require(evidence_complete is True, "GREEN catalog acceptance requires complete evidence")
        require(data.get("decision") == GREEN, "GREEN catalog decision drift")
    else:
        require(data.get("decision") == PENDING, "pending catalog decision drift")
        require(evidence_complete is False, "pending catalog evidence cannot claim complete evidence")

    if evidence_complete:
        require(acceptance_green is True, "complete catalog evidence must resolve to GREEN acceptance")

    if expect_pending is True:
        require(all(checks[key] is False for key in CHECK_KEYS), "pending template cannot pre-claim catalog checks")
        require(refs == [], "pending template cannot pre-claim evidence references")
        require(evidence_complete is False and acceptance_green is False, "pending template must remain fail-closed")


def validate_contract() -> None:
    schema = load(SCHEMA)
    template = load(TEMPLATE)
    decision = load(DECISION)
    go_no_go = load(GO_NO_GO)

    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "schema draft drift")
    require(schema.get("additionalProperties") is False, "schema must reject unknown top-level fields")
    required = set(schema.get("required") or [])
    for field in ("version", "scope_ref", "source_ref", "products", "checks", "evidence_refs", "contains_secret_material", "authority", "evidence_complete", "acceptance_green", "decision"):
        require(field in required, f"schema required field missing: {field}")

    props = schema.get("properties") or {}
    require(props.get("version", {}).get("const") == "ruby-catalog-publication-evidence-v1", "schema version const drift")
    require(props.get("contains_secret_material", {}).get("const") is False, "schema must forbid secret material")
    schema_authority = props.get("authority", {}).get("properties") or {}
    for key in AUTHORITY_KEYS:
        require(schema_authority.get(key, {}).get("const") is False, f"schema authority expanded: {key}")

    validate_evidence(template, expect_pending=True)

    scope = decision.get("approved_scope") or {}
    require(scope.get("source_ref") == template["source_ref"], "CEO-approved source ref drift")
    require(set(scope.get("products") or []) == PRODUCTS, "CEO-approved product scope drift")
    require(scope.get("sprint3_scope_approval_green") is True, "CEO provisional catalog scope approval regressed")
    require(scope.get("publication_catalog_content_complete") is False, "publication content became complete without evidence")
    decision_authority = decision.get("authority") or {}
    for key in AUTHORITY_KEYS:
        require(decision_authority.get(key) is False, f"CEO decision authority expanded: {key}")

    required_text = set(decision.get("remaining_publication_requirements") or [])
    require("final bilingual customer-facing copy" in required_text, "bilingual copy requirement missing")
    require("verified product media references" in required_text, "media requirement missing")
    require("final fulfillment and package/shipping classifications" in required_text, "fulfillment/package requirement missing")
    require("separate subsystem preflight and controlled publication acceptance" in required_text, "publication preflight requirement missing")

    gates = go_no_go.get("required_launch_gates") or {}
    execution = go_no_go.get("execution") or {}
    require(gates.get("final_production_catalog_ready") is False, "final production catalog became GREEN without evidence")
    require(execution.get("production_catalog_mutation_ready") is False, "catalog mutation became ready without evidence")
    require(execution.get("production_launch_ready") is False, "production launch became ready without final gates")

    print("PHIL_AI_OS_CATALOG_PUBLICATION_EVIDENCE_CONTRACT_GREEN template=pending authority=false facts_not_invented=true")


def self_test() -> None:
    base = load(TEMPLATE)
    good = copy.deepcopy(base)
    for key in CHECK_KEYS:
        good["checks"][key] = True
    good["evidence_refs"] = ["synthetic:self-test/catalog-publication"]
    good["evidence_complete"] = True
    good["acceptance_green"] = True
    good["decision"] = GREEN
    validate_evidence(good)

    partial = copy.deepcopy(good)
    partial["checks"]["verified_product_media_references_confirmed"] = False
    try:
        validate_evidence(partial)
    except SystemExit:
        pass
    else:
        fail("self-test accepted incomplete catalog publication evidence")

    authority_drift = copy.deepcopy(good)
    authority_drift["authority"]["production_publish_authorized"] = True
    try:
        validate_evidence(authority_drift)
    except SystemExit:
        pass
    else:
        fail("self-test accepted expanded publication authority")

    print("PHIL_AI_OS_CATALOG_PUBLICATION_EVIDENCE_SELF_TEST_GREEN")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, help="Validate populated catalog publication evidence")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    validate_contract()
    if args.self_test:
        self_test()
    if args.evidence is not None:
        validate_evidence(load(args.evidence.resolve()))
        print(f"PHIL_AI_OS_CATALOG_PUBLICATION_EVIDENCE_FILE_GREEN path={args.evidence}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/operations/ruby-final-go-no-go-signoff-evidence.schema.json"
TEMPLATE = ROOT / "ops/readiness/ruby-final-go-no-go-signoff-evidence.template.json"
GO_NO_GO = ROOT / "ops/readiness/ruby-final-go-no-go-gate-2026-09-02.json"
LAUNCH = ROOT / "ops/readiness/sprint7-launch-acceptance.json"

CHECK_KEYS = (
    "final_production_catalog_ready",
    "final_checkout_tokushoho_payment_shipping_sync_green",
    "komoju_live_acceptance_green",
    "first_party_quick_pickup_production_ready",
    "near_cutover_recovery_freshness_green",
    "main_branch_protection_or_ruleset_green",
    "public_cutover_plan_confirmed",
    "current_head_ci_green",
)
AUTHORITY_KEYS = (
    "production_launch_authorized",
    "dns_cutover_authorized",
    "production_publish_authorized",
    "payment_execution_authorized",
    "order_creation_authorized",
    "automatic_production_execution_authorized",
)
PENDING = "PENDING_FINAL_GO_NO_GO_SIGNOFF_FAIL_CLOSED"
COMPLETE = "FINAL_GO_NO_GO_SIGNOFF_EVIDENCE_COMPLETE"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_FINAL_GO_NO_GO_SIGNOFF_EVIDENCE_FAILED: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_evidence(data: dict, *, expect_pending: bool | None = None) -> None:
    require(data.get("version") == "ruby-final-go-no-go-signoff-evidence-v1", "evidence version drift")
    require(data.get("contains_secret_material") is False, "secret material must not be retained")

    checks = data.get("checks")
    require(isinstance(checks, dict) and set(checks) == set(CHECK_KEYS), "signoff check set drift")
    require(all(isinstance(checks[key], bool) for key in CHECK_KEYS), "signoff checks must be boolean")

    refs = data.get("evidence_refs")
    require(isinstance(refs, list), "evidence_refs must be a list")
    require(all(isinstance(item, str) and item for item in refs), "evidence_refs must be non-empty strings")
    require(len(refs) == len(set(refs)), "evidence_refs must be unique")

    authority = data.get("authority")
    require(isinstance(authority, dict) and set(authority) == set(AUTHORITY_KEYS), "authority field set drift")
    for key in AUTHORITY_KEYS:
        require(authority[key] is False, f"authority expanded: {key}")

    complete = data.get("evidence_complete")
    ceo = data.get("ceo_go_no_go_accepted")
    cto = data.get("cto_signoff_recorded")
    require(isinstance(complete, bool) and isinstance(ceo, bool) and isinstance(cto, bool), "signoff flags must be boolean")

    prerequisites = all(checks[key] is True for key in CHECK_KEYS)
    if complete or ceo or cto:
        require(prerequisites, "signoff cannot outrun required launch gates and current-head CI")
        require(complete is True and ceo is True and cto is True, "final signoff evidence must be complete and include both CEO and CTO")
        require(len(refs) > 0, "final signoff requires evidence references")
        require(data.get("decision") == COMPLETE, "complete signoff decision drift")
    else:
        require(data.get("decision") == PENDING, "pending signoff decision drift")

    if expect_pending is True:
        require(complete is False and ceo is False and cto is False, "pending template cannot pre-claim signoff")
        require(refs == [], "pending template cannot pre-claim signoff evidence")


def validate_contract() -> None:
    schema = load(SCHEMA)
    template = load(TEMPLATE)
    go = load(GO_NO_GO)
    launch = load(LAUNCH)

    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "schema draft drift")
    require(schema.get("additionalProperties") is False, "schema must reject unknown top-level fields")
    schema_authority = (schema.get("properties") or {}).get("authority", {}).get("properties") or {}
    for key in AUTHORITY_KEYS:
        require(schema_authority.get(key, {}).get("const") is False, f"schema authority expanded: {key}")

    validate_evidence(template, expect_pending=True)

    gates = go.get("required_launch_gates") or {}
    expected = {
        "final_production_catalog_ready": gates.get("final_production_catalog_ready"),
        "final_checkout_tokushoho_payment_shipping_sync_green": gates.get("final_checkout_tokushoho_payment_shipping_sync_green"),
        "komoju_live_acceptance_green": gates.get("komoju_live_acceptance_green"),
        "first_party_quick_pickup_production_ready": gates.get("first_party_quick_pickup_production_ready"),
        "near_cutover_recovery_freshness_green": gates.get("near_cutover_recovery_freshness_green"),
        "main_branch_protection_or_ruleset_green": gates.get("main_branch_protection_or_ruleset_green"),
        "public_cutover_plan_confirmed": gates.get("public_cutover_plan_confirmed"),
    }
    for key, value in expected.items():
        require(template["checks"][key] is value, f"pending signoff template does not mirror current Go/No-Go gate: {key}")
    require(template["checks"]["current_head_ci_green"] is False, "pending template cannot pre-claim final current-head CI")

    require(gates.get("final_ceo_go_no_go_accepted") is False, "CEO final Go/No-Go changed without signoff evidence")
    remaining = launch.get("remaining_launch_gates") or {}
    require(remaining.get("final_ceo_go_no_go_accepted") is False, "launch acceptance pre-claimed CEO final Go/No-Go")
    require(remaining.get("cto_signoff_recorded") is False, "launch acceptance pre-claimed CTO signoff")
    require((launch.get("authority_baseline") or {}).get("live_launch_authorized_by_readiness") is False, "launch authority expanded before signoff")
    require((go.get("execution") or {}).get("production_launch_ready") is False, "production launch became ready before signoff")

    print("PHIL_AI_OS_FINAL_GO_NO_GO_SIGNOFF_EVIDENCE_CONTRACT_GREEN signoff=pending authority=false")


def self_test() -> None:
    base = load(TEMPLATE)
    good = copy.deepcopy(base)
    for key in CHECK_KEYS:
        good["checks"][key] = True
    good["evidence_refs"] = ["synthetic:self-test/final-go-no-go"]
    good["evidence_complete"] = True
    good["ceo_go_no_go_accepted"] = True
    good["cto_signoff_recorded"] = True
    good["decision"] = COMPLETE
    validate_evidence(good)

    partial = copy.deepcopy(good)
    partial["checks"]["main_branch_protection_or_ruleset_green"] = False
    try:
        validate_evidence(partial)
    except SystemExit:
        pass
    else:
        fail("self-test accepted signoff with a RED launch gate")

    authority_drift = copy.deepcopy(good)
    authority_drift["authority"]["production_launch_authorized"] = True
    try:
        validate_evidence(authority_drift)
    except SystemExit:
        pass
    else:
        fail("self-test accepted expanded launch authority")

    print("PHIL_AI_OS_FINAL_GO_NO_GO_SIGNOFF_EVIDENCE_SELF_TEST_GREEN")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, help="Validate populated final Go/No-Go signoff evidence")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    validate_contract()
    if args.self_test:
        self_test()
    if args.evidence is not None:
        validate_evidence(load(args.evidence.resolve()))
        print(f"PHIL_AI_OS_FINAL_GO_NO_GO_SIGNOFF_EVIDENCE_FILE_GREEN path={args.evidence}")


if __name__ == "__main__":
    main()

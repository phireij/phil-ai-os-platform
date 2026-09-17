#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/operations/ruby-public-cutover-plan-evidence.schema.json"
TEMPLATE = ROOT / "ops/readiness/ruby-public-cutover-plan-evidence.template.json"
GO_NO_GO = ROOT / "ops/readiness/ruby-final-go-no-go-gate-2026-09-02.json"
DEPLOYMENT = ROOT / "ops/readiness/sprint7-production-deployment-readiness.json"
RUNBOOK = ROOT / "docs/SPRINT_7_WOOCOMMERCE_STAGING_CUTOVER_RUNBOOK_2026-08-28.md"

CHECK_KEYS = (
    "applicable_launch_gates_green",
    "final_catalog_version_confirmed",
    "near_cutover_recovery_green",
    "main_branch_protection_green",
    "rollback_abort_path_confirmed",
    "ssl_domain_readiness_confirmed",
    "cutover_window_and_operator_confirmed",
    "pre_cutover_smoke_plan_confirmed",
    "post_cutover_smoke_plan_confirmed",
    "ceo_final_go_no_go_accepted",
    "cto_signoff_recorded",
)
AUTHORITY_KEYS = (
    "dns_cutover_authorized",
    "site_cutover_authorized",
    "production_publish_authorized",
    "payment_execution_authorized",
    "order_creation_authorized",
    "automatic_production_execution_authorized",
    "automatic_rollback_authorized",
)
PENDING = "PENDING_PUBLIC_CUTOVER_PLAN_CONFIRMATION_FAIL_CLOSED"
GREEN = "PUBLIC_CUTOVER_PLAN_CONFIRMED_GREEN"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_PUBLIC_CUTOVER_PLAN_EVIDENCE_FAILED: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_evidence(data: dict, *, expect_pending: bool | None = None) -> None:
    require(data.get("version") == "ruby-public-cutover-plan-evidence-v1", "evidence version drift")
    require(data.get("runbook_ref") == "docs/SPRINT_7_WOOCOMMERCE_STAGING_CUTOVER_RUNBOOK_2026-08-28.md", "runbook ref drift")
    require(data.get("contains_secret_material") is False, "secret material must not be retained")

    checks = data.get("checks")
    require(isinstance(checks, dict), "checks object missing")
    require(set(checks) == set(CHECK_KEYS), "cutover check set drift")
    require(all(isinstance(checks[key], bool) for key in CHECK_KEYS), "cutover checks must be boolean")

    authority = data.get("authority")
    require(isinstance(authority, dict), "authority object missing")
    require(set(authority) == set(AUTHORITY_KEYS), "authority field set drift")
    for key in AUTHORITY_KEYS:
        require(authority[key] is False, f"authority expanded: {key}")

    refs = data.get("evidence_refs")
    require(isinstance(refs, list), "evidence_refs must be a list")
    require(all(isinstance(item, str) and item for item in refs), "evidence_refs must contain non-empty strings")
    require(len(refs) == len(set(refs)), "evidence_refs must be unique")

    complete = data.get("evidence_complete")
    green = data.get("confirmation_green")
    require(isinstance(complete, bool), "evidence_complete must be boolean")
    require(isinstance(green, bool), "confirmation_green must be boolean")

    prerequisites = all(checks[key] is True for key in CHECK_KEYS) and len(refs) > 0
    if green:
        require(prerequisites, "GREEN cutover plan confirmation requires every prerequisite and evidence")
        require(complete is True, "GREEN cutover plan confirmation requires complete evidence")
        require(data.get("decision") == GREEN, "GREEN cutover plan decision drift")
    else:
        require(data.get("decision") == PENDING, "pending cutover plan decision drift")
        require(complete is False, "pending cutover evidence cannot claim complete evidence")

    if complete:
        require(green is True, "complete cutover plan evidence must resolve to GREEN confirmation")

    if expect_pending is True:
        require(all(checks[key] is False for key in CHECK_KEYS), "pending template cannot pre-claim cutover checks")
        require(refs == [], "pending template cannot pre-claim evidence references")
        require(complete is False and green is False, "pending template must remain fail-closed")


def validate_contract() -> None:
    schema = load(SCHEMA)
    template = load(TEMPLATE)
    go = load(GO_NO_GO)
    deployment = load(DEPLOYMENT)
    runbook = RUNBOOK.read_text(encoding="utf-8")

    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "schema draft drift")
    require(schema.get("additionalProperties") is False, "schema must reject unknown top-level fields")
    props = schema.get("properties") or {}
    schema_authority = props.get("authority", {}).get("properties") or {}
    for key in AUTHORITY_KEYS:
        require(schema_authority.get(key, {}).get("const") is False, f"schema authority expanded: {key}")

    validate_evidence(template, expect_pending=True)

    woo = deployment.get("woocommerce") or {}
    require(woo.get("dns_or_site_cutover_authorized") is False, "deployment state unexpectedly authorizes DNS/site cutover")
    require(woo.get("live_mutation_authorized") is False, "deployment state unexpectedly authorizes live mutation")
    require(woo.get("rollback_plan_required") is True, "rollback requirement missing")
    require(woo.get("ssl_verified") is True, "preproduction SSL baseline regressed")

    gates = go.get("required_launch_gates") or {}
    require(gates.get("public_cutover_plan_confirmed") is False, "public cutover plan became confirmed without evidence")
    require(gates.get("final_ceo_go_no_go_accepted") is False, "final CEO Go/No-Go changed prematurely")
    require(gates.get("main_branch_protection_or_ruleset_green") is False, "branch-protection gate changed prematurely")
    execution = go.get("execution") or {}
    require(execution.get("dns_cutover_ready") is False, "DNS cutover became ready without final gates")
    require(execution.get("production_launch_ready") is False, "production launch became ready without final gates")

    for phrase in (
        "DNS/public cutover is last",
        "rollback/abort path confirmed",
        "public cutover plan confirmed",
        "final CEO Go/No-Go and CTO sign-off",
        "This runbook does not authorize public DNS/site changes",
    ):
        require(phrase in runbook, f"cutover runbook safeguard missing: {phrase}")

    print("PHIL_AI_OS_PUBLIC_CUTOVER_PLAN_EVIDENCE_CONTRACT_GREEN template=pending dns_authority=false")


def self_test() -> None:
    base = load(TEMPLATE)
    good = copy.deepcopy(base)
    for key in CHECK_KEYS:
        good["checks"][key] = True
    good["evidence_refs"] = ["synthetic:self-test/public-cutover-plan"]
    good["evidence_complete"] = True
    good["confirmation_green"] = True
    good["decision"] = GREEN
    validate_evidence(good)

    partial = copy.deepcopy(good)
    partial["checks"]["main_branch_protection_green"] = False
    try:
        validate_evidence(partial)
    except SystemExit:
        pass
    else:
        fail("self-test accepted incomplete cutover plan evidence")

    authority_drift = copy.deepcopy(good)
    authority_drift["authority"]["dns_cutover_authorized"] = True
    try:
        validate_evidence(authority_drift)
    except SystemExit:
        pass
    else:
        fail("self-test accepted expanded DNS authority")

    print("PHIL_AI_OS_PUBLIC_CUTOVER_PLAN_EVIDENCE_SELF_TEST_GREEN")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, help="Validate populated public cutover plan evidence")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    validate_contract()
    if args.self_test:
        self_test()
    if args.evidence is not None:
        validate_evidence(load(args.evidence.resolve()))
        print(f"PHIL_AI_OS_PUBLIC_CUTOVER_PLAN_EVIDENCE_FILE_GREEN path={args.evidence}")


if __name__ == "__main__":
    main()

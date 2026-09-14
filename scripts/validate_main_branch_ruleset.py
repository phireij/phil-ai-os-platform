#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "governance/github/main-branch-protection-policy.json"


class RulesetValidationError(ValueError):
    pass


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rules_by_type(ruleset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rules = ruleset.get("rules")
    if not isinstance(rules, list):
        raise RulesetValidationError("ruleset rules must be a list")
    result: dict[str, dict[str, Any]] = {}
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("type"), str):
            raise RulesetValidationError("ruleset contains malformed rule")
        result[rule["type"]] = rule
    return result


def _targets_main(ruleset: dict[str, Any]) -> bool:
    if ruleset.get("target") != "branch":
        return False
    conditions = ruleset.get("conditions")
    if not isinstance(conditions, dict):
        return False
    ref_name = conditions.get("ref_name")
    if not isinstance(ref_name, dict):
        return False
    include = ref_name.get("include")
    if not isinstance(include, list):
        return False
    return any(item in {"refs/heads/main", "~DEFAULT_BRANCH"} for item in include)


def _validate_pull_request_policy(name: str, pr_params: dict[str, Any], policy: dict[str, Any]) -> str | None:
    expected_pr = policy.get("pull_request")
    if not isinstance(expected_pr, dict):
        return f"{name}: policy pull_request configuration is invalid"

    minimum_approvals = expected_pr.get("minimum_approving_review_count", 0)
    if not isinstance(minimum_approvals, int) or minimum_approvals < 0:
        return f"{name}: policy minimum_approving_review_count is invalid"

    actual_approvals = pr_params.get("required_approving_review_count")
    if not isinstance(actual_approvals, int) or actual_approvals < minimum_approvals:
        return f"{name}: fewer than {minimum_approvals} approving reviews required"

    if expected_pr.get("require_code_owner_review") is True and pr_params.get("require_code_owner_review") is not True:
        return f"{name}: code owner review is not required"

    if expected_pr.get("require_last_push_approval") is True and pr_params.get("require_last_push_approval") is not True:
        return f"{name}: last push approval is not required"

    if expected_pr.get("required_review_thread_resolution") is True and pr_params.get("required_review_thread_resolution") is not True:
        return f"{name}: review thread resolution is not required"

    return None


def validate_rulesets(rulesets: Any, policy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(rulesets, list):
        raise RulesetValidationError("rulesets snapshot must be a list")
    candidates = [item for item in rulesets if isinstance(item, dict) and _targets_main(item)]
    if not candidates:
        raise RulesetValidationError("no branch ruleset targets main")

    required_types = set(policy.get("required_rule_types", []))
    required_contexts = set(policy.get("required_status_check_contexts", []))
    required_enforcement = policy.get("required_enforcement")
    min_checks = policy.get("minimum_required_status_checks", 0)
    if not isinstance(min_checks, int) or min_checks < 0:
        raise RulesetValidationError("policy minimum_required_status_checks is invalid")

    failures: list[str] = []
    for ruleset in candidates:
        name = str(ruleset.get("name") or "unnamed")
        if ruleset.get("enforcement") != required_enforcement:
            failures.append(f"{name}: enforcement is not {required_enforcement}")
            continue
        try:
            by_type = _rules_by_type(ruleset)
        except RulesetValidationError as exc:
            failures.append(f"{name}: {exc}")
            continue
        missing_types = sorted(required_types - set(by_type))
        if missing_types:
            failures.append(f"{name}: missing rule types {','.join(missing_types)}")
            continue

        status_rule = by_type.get("required_status_checks", {})
        parameters = status_rule.get("parameters")
        checks = parameters.get("required_status_checks") if isinstance(parameters, dict) else None
        if not isinstance(checks, list):
            failures.append(f"{name}: required_status_checks parameters missing")
            continue
        contexts = {
            item.get("context")
            for item in checks
            if isinstance(item, dict) and isinstance(item.get("context"), str)
        }
        if len(contexts) < min_checks:
            failures.append(f"{name}: fewer than {min_checks} required status checks")
            continue
        missing_contexts = sorted(required_contexts - contexts)
        if missing_contexts:
            failures.append(f"{name}: missing required contexts {','.join(missing_contexts)}")
            continue

        pull_request_rule = by_type.get("pull_request", {})
        pr_params = pull_request_rule.get("parameters")
        if not isinstance(pr_params, dict):
            failures.append(f"{name}: pull_request parameters missing")
            continue
        pr_failure = _validate_pull_request_policy(name, pr_params, policy)
        if pr_failure is not None:
            failures.append(pr_failure)
            continue

        return {
            "status": "green",
            "ruleset_name": name,
            "target_branch": policy.get("target_branch"),
            "required_rule_types": sorted(required_types),
            "required_status_check_contexts": sorted(required_contexts),
            "production_authority_effect": "none",
        }

    raise RulesetValidationError("; ".join(failures) if failures else "no compliant main ruleset found")


def _sample_ruleset(
    *,
    enforcement: str = "active",
    include_checks: bool = True,
    approvals: int = 0,
    code_owner_review: bool = False,
    last_push_approval: bool = False,
    review_thread_resolution: bool = True,
) -> dict[str, Any]:
    checks = [
        {"context": "integrated-contract-regression"},
        {"context": "isolated-runtime-smoke"},
    ] if include_checks else [{"context": "integrated-contract-regression"}]
    return {
        "id": 1,
        "name": "Phil AI OS main launch protection",
        "target": "branch",
        "enforcement": enforcement,
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": approvals,
                    "dismiss_stale_reviews_on_push": False,
                    "require_code_owner_review": code_owner_review,
                    "require_last_push_approval": last_push_approval,
                    "required_review_thread_resolution": review_thread_resolution,
                },
            },
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "do_not_enforce_on_create": False,
                    "required_status_checks": checks,
                },
            },
        ],
    }


def _expect_failure(rulesets: Any, policy: dict[str, Any], expected: str) -> None:
    try:
        validate_rulesets(rulesets, policy)
    except RulesetValidationError as exc:
        if expected not in str(exc):
            raise AssertionError(f"expected {expected!r}, got {exc!r}") from exc
    else:
        raise AssertionError(f"invalid ruleset unexpectedly passed: {expected}")


def self_test(policy: dict[str, Any]) -> None:
    result = validate_rulesets([_sample_ruleset()], policy)
    assert result["status"] == "green"
    _expect_failure([], policy, "no branch ruleset targets main")
    _expect_failure([_sample_ruleset(enforcement="evaluate")], policy, "enforcement is not active")
    _expect_failure([_sample_ruleset(include_checks=False)], policy, "fewer than 2 required status checks")
    _expect_failure([_sample_ruleset(review_thread_resolution=False)], policy, "review thread resolution is not required")

    stricter_policy = json.loads(json.dumps(policy))
    stricter_policy["pull_request"]["minimum_approving_review_count"] = 1
    _expect_failure([_sample_ruleset(approvals=0)], stricter_policy, "fewer than 1 approving reviews required")
    assert validate_rulesets([_sample_ruleset(approvals=1)], stricter_policy)["status"] == "green"

    stricter_policy = json.loads(json.dumps(policy))
    stricter_policy["pull_request"]["require_code_owner_review"] = True
    _expect_failure([_sample_ruleset()], stricter_policy, "code owner review is not required")
    assert validate_rulesets([_sample_ruleset(code_owner_review=True)], stricter_policy)["status"] == "green"

    stricter_policy = json.loads(json.dumps(policy))
    stricter_policy["pull_request"]["require_last_push_approval"] = True
    _expect_failure([_sample_ruleset()], stricter_policy, "last push approval is not required")
    assert validate_rulesets([_sample_ruleset(last_push_approval=True)], stricter_policy)["status"] == "green"

    print("PHIL_AI_OS_MAIN_BRANCH_RULESET_VALIDATOR_SELF_TEST_GREEN authority_effect=none")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rulesets", type=Path, help="JSON snapshot from GitHub repository rulesets API")
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    policy = _load_json(args.policy)
    if args.self_test:
        self_test(policy)
        return
    if args.rulesets is None:
        raise SystemExit("--rulesets is required unless --self-test is used")
    try:
        result = validate_rulesets(_load_json(args.rulesets), policy)
    except RulesetValidationError as exc:
        raise SystemExit(f"PHIL_AI_OS_MAIN_BRANCH_RULESET_NOT_READY: {exc}") from exc
    print("PHIL_AI_OS_MAIN_BRANCH_RULESET_GREEN " + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

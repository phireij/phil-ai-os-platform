from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ALLOWED_ACTIONS = {"create_candidate", "update_candidate", "noop"}


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if plan.get("version") != "ruby-preproduction-catalog-dry-run-plan-v1":
        blockers.append("plan version mismatch")
    if plan.get("plan_only") is not True:
        blockers.append("plan_only must remain true")
    if plan.get("network_calls_performed") is not False:
        blockers.append("catalog plan must not perform network calls")
    if plan.get("automatic_deletions_planned") is not False:
        blockers.append("automatic deletion is forbidden")
    if plan.get("mutation_authorized") is not False:
        blockers.append("catalog plan must not carry mutation authority")
    if plan.get("production_publish_authorized") is not False:
        blockers.append("catalog plan must not carry publication authority")
    if plan.get("media_reconciliation_requires_review") is not True:
        blockers.append("media reconciliation must remain review-required")

    for field in ("category_actions", "product_actions", "existing_unmatched_skus", "blockers"):
        if not isinstance(plan.get(field), list):
            blockers.append(f"{field} must be a list")

    for collection in ("category_actions", "product_actions"):
        values = plan.get(collection)
        if isinstance(values, list):
            for index, item in enumerate(values):
                if not isinstance(item, dict):
                    blockers.append(f"{collection}[{index}] must be an object")
                    continue
                action = item.get("action")
                if action not in ALLOWED_ACTIONS:
                    blockers.append(f"{collection}[{index}] contains forbidden action {action!r}")
                changes = item.get("changes")
                if not isinstance(changes, list):
                    blockers.append(f"{collection}[{index}].changes must be a list")

    unmatched = plan.get("existing_unmatched_skus")
    if isinstance(unmatched, list):
        if any(not isinstance(sku, str) or not sku for sku in unmatched):
            blockers.append("existing_unmatched_skus must contain non-empty strings")
        if unmatched and plan.get("automatic_deletions_planned") is not False:
            blockers.append("unmatched SKUs can never imply automatic deletion")

    return {
        "version": "ruby-preproduction-catalog-dry-run-plan-acceptance-v1",
        "accepted_for_human_review": not blockers,
        "blockers": blockers,
        "mutation_authorized": False,
        "production_publish_authorized": False,
        "execution_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate that a catalog dry-run plan is review-only and non-authorizing.")
    parser.add_argument("plan_json", type=Path)
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.plan_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result = {
            "version": "ruby-preproduction-catalog-dry-run-plan-acceptance-v1",
            "accepted_for_human_review": False,
            "blockers": [f"input load failed: {exc}"],
            "mutation_authorized": False,
            "production_publish_authorized": False,
            "execution_authorized": False,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    if not isinstance(payload, dict):
        result = {
            "version": "ruby-preproduction-catalog-dry-run-plan-acceptance-v1",
            "accepted_for_human_review": False,
            "blockers": ["plan root must be a JSON object"],
            "mutation_authorized": False,
            "production_publish_authorized": False,
            "execution_authorized": False,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    result = validate_plan(payload)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["accepted_for_human_review"]:
        print("PHIL_AI_OS_CATALOG_DRY_RUN_PLAN_ACCEPTED_FOR_REVIEW execution_authorized=false mutation_authorized=false")
        return 0
    print(
        "PHIL_AI_OS_CATALOG_DRY_RUN_PLAN_REJECTED "
        f"blockers={len(result['blockers'])} execution_authorized=false mutation_authorized=false"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

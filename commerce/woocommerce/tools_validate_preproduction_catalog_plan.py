from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ALLOWED_ACTIONS = {"create_candidate", "update_candidate", "noop"}


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(_non_empty_string(item) for item in value)


def _validate_category_action(item: dict[str, Any], label: str, blockers: list[str]) -> None:
    desired = item.get("desired")
    if not isinstance(desired, dict):
        blockers.append(f"{label}.desired must be an object")
        return
    for field in ("key", "name", "slug"):
        if not _non_empty_string(desired.get(field)):
            blockers.append(f"{label}.desired.{field} must be a non-empty string")
    parent_key = desired.get("parent_key")
    if parent_key is not None and not _non_empty_string(parent_key):
        blockers.append(f"{label}.desired.parent_key must be null or a non-empty string")


def _validate_product_action(item: dict[str, Any], label: str, blockers: list[str]) -> None:
    sku = item.get("sku")
    if not _non_empty_string(sku):
        blockers.append(f"{label}.sku must be a non-empty string")
    desired = item.get("desired")
    if not isinstance(desired, dict):
        blockers.append(f"{label}.desired must be an object")
        return
    for field in ("sku", "name", "slug", "regular_price", "status", "catalog_visibility", "shipping_class"):
        if not _non_empty_string(desired.get(field)):
            blockers.append(f"{label}.desired.{field} must be a non-empty string")
    if _non_empty_string(sku) and desired.get("sku") != sku:
        blockers.append(f"{label}.desired.sku must match action sku")
    if desired.get("status") != "draft":
        blockers.append(f"{label}.desired.status must remain draft for controlled review")
    if desired.get("catalog_visibility") != "hidden":
        blockers.append(
            f"{label}.desired.catalog_visibility must remain hidden for controlled review"
        )
    for field in ("category_slugs", "media_keys"):
        if not _string_list(desired.get(field)):
            blockers.append(f"{label}.desired.{field} must contain non-empty strings")


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if plan.get("version") != "ruby-preproduction-catalog-dry-run-plan-v1":
        blockers.append("plan version mismatch")
    if plan.get("plan_only") is not True:
        blockers.append("plan_only must remain true")
    if plan.get("network_calls_performed") is not False:
        blockers.append("catalog plan must not perform network calls")
    if plan.get("owner_package_ready") is not True:
        blockers.append("owner package must be ready before human review")
    if plan.get("snapshot_accepted") is not True:
        blockers.append("read-only catalog snapshot must be accepted before human review")
    if plan.get("ready_for_controlled_review") is not True:
        blockers.append("catalog plan must be ready for controlled review")
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

    source_blockers = plan.get("blockers")
    if isinstance(source_blockers, list):
        if any(not _non_empty_string(blocker) for blocker in source_blockers):
            blockers.append("plan blockers must contain non-empty strings")
        if source_blockers:
            blockers.append("catalog plan carries blockers and is not ready for human review")

    for collection in ("category_actions", "product_actions"):
        values = plan.get(collection)
        if isinstance(values, list):
            for index, item in enumerate(values):
                label = f"{collection}[{index}]"
                if not isinstance(item, dict):
                    blockers.append(f"{label} must be an object")
                    continue
                action = item.get("action")
                if action not in ALLOWED_ACTIONS:
                    blockers.append(f"{label} contains forbidden action {action!r}")
                changes = item.get("changes")
                if not isinstance(changes, list):
                    blockers.append(f"{label}.changes must be a list")
                else:
                    if any(not _non_empty_string(change) for change in changes):
                        blockers.append(f"{label}.changes must contain non-empty strings")
                    if len(changes) != len(set(changes)):
                        blockers.append(f"{label}.changes must not contain duplicates")
                    if action == "noop" and changes:
                        blockers.append(f"{label} noop action must not carry changes")
                    if action in {"create_candidate", "update_candidate"} and not changes:
                        blockers.append(f"{label} {action} must carry at least one change")
                    if action == "create_candidate" and "missing_in_snapshot" not in changes:
                        blockers.append(f"{label} create_candidate must include missing_in_snapshot")
                    if action == "update_candidate" and "missing_in_snapshot" in changes:
                        blockers.append(f"{label} update_candidate cannot include missing_in_snapshot")
                if collection == "category_actions":
                    _validate_category_action(item, label, blockers)
                else:
                    _validate_product_action(item, label, blockers)

    unmatched = plan.get("existing_unmatched_skus")
    if isinstance(unmatched, list):
        if any(not _non_empty_string(sku) for sku in unmatched):
            blockers.append("existing_unmatched_skus must contain non-empty strings")
        if len(unmatched) != len(set(unmatched)):
            blockers.append("existing_unmatched_skus must not contain duplicates")
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

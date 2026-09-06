from __future__ import annotations

import argparse
from datetime import datetime
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
VALIDATOR_PATH = ROOT / "tools_validate_owner_catalog_package.py"
spec = importlib.util.spec_from_file_location("owner_catalog_validator", VALIDATOR_PATH)
owner_catalog_validator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(owner_catalog_validator)


def _blocked(reason: str, *, validation: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "version": "ruby-preproduction-catalog-dry-run-plan-v1",
        "plan_only": True,
        "network_calls_performed": False,
        "owner_package_ready": bool(validation and validation.get("ready_for_preproduction_configuration")),
        "snapshot_accepted": False,
        "ready_for_controlled_review": False,
        "blockers": [reason],
        "category_actions": [],
        "product_actions": [],
        "existing_unmatched_skus": [],
        "automatic_deletions_planned": False,
        "media_reconciliation_requires_review": True,
        "mutation_authorized": False,
        "production_publish_authorized": False,
    }


def _has_timezone_iso_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _validate_snapshot(snapshot: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if snapshot.get("schema_version") != "1.0":
        blockers.append("snapshot schema_version must be 1.0")
    if snapshot.get("scope") != "woocommerce_catalog_metadata_read_only":
        blockers.append("snapshot scope must be woocommerce_catalog_metadata_read_only")
    if not _has_timezone_iso_timestamp(snapshot.get("captured_at")):
        blockers.append("snapshot captured_at must be a timezone-aware ISO timestamp")
    if snapshot.get("network_read_only") is not True:
        blockers.append("snapshot must be network_read_only")
    if snapshot.get("mutation_authorized") is not False:
        blockers.append("snapshot must not carry mutation authority")
    if snapshot.get("production_publish_authorized") is not False:
        blockers.append("snapshot must not carry publication authority")

    products = snapshot.get("products")
    categories = snapshot.get("categories")

    snapshot_category_slugs: set[str] = set()
    if isinstance(categories, list):
        for item in categories:
            if isinstance(item, dict):
                slug_value = item.get("slug")
                if isinstance(slug_value, str) and slug_value.strip():
                    snapshot_category_slugs.add(slug_value.strip())

    if not isinstance(products, list):
        blockers.append("snapshot products must be a list")
    else:
        seen_skus: set[str] = set()
        seen_product_slugs: set[str] = set()
        for index, item in enumerate(products, start=1):
            if not isinstance(item, dict):
                blockers.append(f"snapshot product[{index}] must be an object")
                continue
            sku_value = item.get("sku")
            if not isinstance(sku_value, str) or not sku_value.strip():
                blockers.append(f"snapshot product[{index}] requires explicit string SKU")
                continue
            sku = sku_value.strip()
            if sku in seen_skus:
                blockers.append(f"snapshot contains duplicate product SKU: {sku}")
            seen_skus.add(sku)

            for field in ("name", "slug", "regular_price", "status", "catalog_visibility", "shipping_class"):
                if field in item and not isinstance(item[field], str):
                    blockers.append(f"snapshot product[{index}].{field} must be a string")

            slug_value = item.get("slug")
            if isinstance(slug_value, str) and slug_value.strip():
                slug = slug_value.strip()
                if slug in seen_product_slugs:
                    blockers.append(f"snapshot contains duplicate product slug: {slug}")
                seen_product_slugs.add(slug)

            product_categories = item.get("categories", [])
            if not isinstance(product_categories, list):
                blockers.append(f"snapshot product[{index}].categories must be a list")
            else:
                seen_product_category_slugs: set[str] = set()
                for category_index, category in enumerate(product_categories, start=1):
                    if not isinstance(category, dict):
                        blockers.append(
                            f"snapshot product[{index}].categories[{category_index}] must be an object"
                        )
                        continue
                    category_slug = category.get("slug")
                    if not isinstance(category_slug, str) or not category_slug.strip():
                        blockers.append(
                            f"snapshot product[{index}].categories[{category_index}] requires explicit string slug"
                        )
                        continue
                    normalized_category_slug = category_slug.strip()
                    if normalized_category_slug in seen_product_category_slugs:
                        blockers.append(
                            f"snapshot product[{index}] contains duplicate category slug: {normalized_category_slug}"
                        )
                    seen_product_category_slugs.add(normalized_category_slug)
                    if normalized_category_slug not in snapshot_category_slugs:
                        blockers.append(
                            f"snapshot product[{index}] references unknown category slug: {normalized_category_slug}"
                        )

    if not isinstance(categories, list):
        blockers.append("snapshot categories must be a list")
    else:
        seen_slugs: set[str] = set()
        for index, item in enumerate(categories, start=1):
            if not isinstance(item, dict):
                blockers.append(f"snapshot category[{index}] must be an object")
                continue
            slug_value = item.get("slug")
            if not isinstance(slug_value, str) or not slug_value.strip():
                blockers.append(f"snapshot category[{index}] requires explicit string slug")
                continue
            slug = slug_value.strip()
            if slug in seen_slugs:
                blockers.append(f"snapshot contains duplicate category slug: {slug}")
            seen_slugs.add(slug)
            if "name" in item and not isinstance(item["name"], str):
                blockers.append(f"snapshot category[{index}].name must be a string")
    return blockers


def _owner_snapshot_slug_collision_blockers(
    owner_payload: dict[str, Any], snapshot: dict[str, Any]
) -> list[str]:
    """Block owner slugs already occupied by a different WooCommerce identity."""

    blockers: list[str] = []
    snapshot_products_by_slug = {
        item["slug"].strip(): item
        for item in snapshot["products"]
        if isinstance(item.get("slug"), str) and item["slug"].strip()
    }
    for product in owner_payload["products"]:
        desired_slug = product["slug"]["en"].strip()
        occupant = snapshot_products_by_slug.get(desired_slug)
        if occupant is None:
            continue
        occupant_sku = occupant["sku"].strip()
        if occupant_sku != product["sku"]:
            blockers.append(
                f"owner product {product['sku']} slug {desired_slug} is already occupied by snapshot SKU {occupant_sku}"
            )
    return blockers


def build_plan(owner_payload: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    validation = owner_catalog_validator.validate_package(owner_payload)
    if not validation.get("ready_for_preproduction_configuration"):
        result = _blocked("owner catalog package is not ready for preproduction configuration", validation=validation)
        result["blockers"].extend(validation.get("blockers", []))
        return result

    snapshot_blockers = _validate_snapshot(snapshot)
    if snapshot_blockers:
        result = _blocked("read-only catalog snapshot is invalid", validation=validation)
        result["blockers"].extend(snapshot_blockers)
        return result

    slug_collision_blockers = _owner_snapshot_slug_collision_blockers(owner_payload, snapshot)
    if slug_collision_blockers:
        result = _blocked("owner catalog conflicts with existing snapshot product slugs", validation=validation)
        result["snapshot_accepted"] = True
        result["blockers"].extend(slug_collision_blockers)
        return result

    owner_categories = owner_payload["categories"]
    owner_products = owner_payload["products"]
    existing_categories = {item["slug"]: item for item in snapshot["categories"]}
    existing_products = {item["sku"]: item for item in snapshot["products"]}

    category_slug_by_key = {
        category["key"]: category["slug"]["en"]
        for category in owner_categories
    }

    category_actions: list[dict[str, Any]] = []
    for category in owner_categories:
        desired_slug = category["slug"]["en"]
        desired_name = category["name"]["en"]
        existing = existing_categories.get(desired_slug)
        desired = {
            "key": category["key"],
            "name": desired_name,
            "slug": desired_slug,
            "parent_key": category.get("parent_key"),
        }
        if existing is None:
            action = "create_candidate"
            changes = ["missing_in_snapshot"]
        else:
            changes = []
            if str(existing.get("name") or "") != desired_name:
                changes.append("name")
            if category.get("parent_key") is not None:
                changes.append("parent_requires_id_resolution")
            action = "update_candidate" if changes else "noop"
        category_actions.append({"action": action, "desired": desired, "changes": changes})

    product_actions: list[dict[str, Any]] = []
    owner_skus: set[str] = set()
    for product in owner_products:
        sku = product["sku"]
        owner_skus.add(sku)
        desired_category_slugs = sorted(category_slug_by_key[key] for key in product["category_keys"])
        desired = {
            "sku": sku,
            "name": product["name"]["en"],
            "slug": product["slug"]["en"],
            "regular_price": product["regular_price"],
            "status": product["status"],
            "catalog_visibility": product["visibility"],
            "shipping_class": product["fulfillment"]["shipping_class"],
            "category_slugs": desired_category_slugs,
            "media_keys": list(product["media_keys"]),
        }
        existing = existing_products.get(sku)
        if existing is None:
            action = "create_candidate"
            changes = ["missing_in_snapshot"]
        else:
            changes = []
            comparisons = {
                "name": str(existing.get("name") or ""),
                "slug": str(existing.get("slug") or ""),
                "regular_price": str(existing.get("regular_price") or ""),
                "status": str(existing.get("status") or ""),
                "catalog_visibility": str(existing.get("catalog_visibility") or ""),
                "shipping_class": str(existing.get("shipping_class") or ""),
            }
            for field, actual in comparisons.items():
                if actual != desired[field]:
                    changes.append(field)
            existing_category_slugs = sorted(
                category["slug"]
                for category in existing.get("categories", [])
            )
            if existing_category_slugs != desired_category_slugs:
                changes.append("categories")
            if desired["media_keys"]:
                changes.append("media_requires_source_ref_reconciliation")
            action = "update_candidate" if changes else "noop"
        product_actions.append({"action": action, "sku": sku, "desired": desired, "changes": changes})

    existing_unmatched_skus = sorted(set(existing_products) - owner_skus)
    blockers: list[str] = []
    if existing_unmatched_skus:
        blockers.append("existing snapshot contains SKUs absent from owner package; no deletion is planned")

    return {
        "version": "ruby-preproduction-catalog-dry-run-plan-v1",
        "plan_only": True,
        "network_calls_performed": False,
        "owner_package_ready": True,
        "snapshot_accepted": True,
        "ready_for_controlled_review": True,
        "blockers": blockers,
        "category_actions": category_actions,
        "product_actions": product_actions,
        "existing_unmatched_skus": existing_unmatched_skus,
        "automatic_deletions_planned": False,
        "media_reconciliation_requires_review": True,
        "mutation_authorized": False,
        "production_publish_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a non-mutating proposed preproduction catalog change plan.")
    parser.add_argument("owner_catalog_json", type=Path)
    parser.add_argument("readonly_snapshot_json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        owner_payload = json.loads(args.owner_catalog_json.read_text(encoding="utf-8"))
        snapshot = json.loads(args.readonly_snapshot_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result = _blocked(f"input load failed: {exc}")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    if not isinstance(owner_payload, dict) or not isinstance(snapshot, dict):
        result = _blocked("both inputs must be JSON objects")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    result = build_plan(owner_payload, snapshot)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    if result["ready_for_controlled_review"]:
        print(
            "PHIL_AI_OS_PREPRODUCTION_CATALOG_DRY_RUN_PLAN_GREEN "
            "plan_only=true network_calls=false automatic_deletions=false mutation_authorized=false"
        )
        return 0

    print(
        "PHIL_AI_OS_PREPRODUCTION_CATALOG_DRY_RUN_PLAN_BLOCKED "
        f"blockers={len(result['blockers'])} mutation_authorized=false",
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from phil_ai_os_woocommerce.models import CategoryRecord, InventoryRecord, MediaRecord, ProductRecord

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"


def validate_schema_file(schema: Path) -> dict[str, object]:
    payload = json.loads(schema.read_text(encoding="utf-8"))
    assert payload.get("$schema") == DRAFT_2020_12, schema
    assert payload.get("type") == "object", schema
    properties = payload.get("properties", {})
    if "mutation_authorized" in properties:
        assert properties["mutation_authorized"].get("const") is False, schema
    return payload


def main() -> int:
    for schema in sorted((ROOT / "schemas").glob("*.schema.json")):
        validate_schema_file(schema)

    shared_contract = REPO_ROOT / "contracts" / "commerce" / "site-migration-source.schema.json"
    validate_schema_file(shared_contract)

    for contract_dir in (REPO_ROOT / "contracts" / "cx", REPO_ROOT / "contracts" / "operations"):
        for schema in sorted(contract_dir.glob("*.schema.json")):
            validate_schema_file(schema)

    fixture = json.loads((ROOT / "fixtures" / "catalog.json").read_text(encoding="utf-8"))
    assert fixture.get("fixture_only") is True
    categories = [CategoryRecord.from_mapping(v) for v in fixture["categories"]]
    media = [MediaRecord.from_mapping(v) for v in fixture["media"]]
    products = [ProductRecord.from_mapping(v) for v in fixture["products"]]
    inventory = [InventoryRecord.from_mapping(v) for v in fixture["inventory"]]

    category_keys = {v.key for v in categories}
    media_keys = {v.key for v in media}
    product_skus = {v.sku for v in products}
    inventory_skus = {v.sku for v in inventory}

    for product in products:
        assert set(product.category_keys).issubset(category_keys)
        assert set(product.media_keys).issubset(media_keys)
    assert inventory_skus.issubset(product_skus)

    migration = json.loads((ROOT / "fixtures" / "site-migration-plan.json").read_text(encoding="utf-8"))
    assert migration["public_domain"] == "https://www.rubyscakedelights.shop/"
    assert migration["source_platform"] == "hostinger-website-builder"
    assert migration["source_role"] == "reference-only"
    assert set(migration["copy_sections"]) == {"store_information", "contact_information", "policies"}
    assert set(migration["exclude_sections"]) == {"products", "categories"}
    assert migration["verification_required"] is True
    assert migration["production_authority"] is False

    ops_fixture = REPO_ROOT / "contracts" / "operations" / "fixtures" / "order-intent.sample.json"
    ops = json.loads(ops_fixture.read_text(encoding="utf-8"))
    assert ops.get("fixture_only") is True
    assert ops.get("mutation_authorized") is False
    assert 0 <= float(ops.get("confidence", -1)) <= 1

    normalized_fixture = REPO_ROOT / "contracts" / "operations" / "fixtures" / "normalized-order-intent.sample.json"
    normalized = json.loads(normalized_fixture.read_text(encoding="utf-8"))
    assert normalized.get("fixture_only") is True
    assert normalized.get("mutation_authorized") is False
    assert normalized.get("fulfillment") == "pickup"
    assert normalized.get("intent_type") in {"order_inquiry", "order_request", "availability_check"}
    assert 0 <= float(normalized.get("confidence", -1)) <= 1
    assert {item["sku"] for item in normalized["items"]}.issubset(product_skus)

    cx_fixture = REPO_ROOT / "contracts" / "cx" / "fixtures" / "checkout-readiness.sample.json"
    cx = json.loads(cx_fixture.read_text(encoding="utf-8"))
    assert cx.get("fixture_only") is True
    assert cx.get("mutation_authorized") is False
    assert isinstance(cx.get("ready"), bool)
    assert {item["sku"] for item in cx["items"]}.issubset(product_skus)
    if cx["ready"]:
        assert cx.get("blockers") == []

    print("PHIL_AI_OS_SPRINT_3_CONTRACT_VALIDATION_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

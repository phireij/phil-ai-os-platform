from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "commerce/woocommerce/fixtures/working-catalog-subset-2026-09-11.json"
OUTPUT = Path(__file__).resolve().parent / "src/ruby-working-catalog-preview.mjs"


def _require_false(source: dict[str, Any], field: str) -> None:
    if source.get(field) is not False:
        raise ValueError(f"working catalog must keep {field}=false")


def build_projection_from_source(source: dict[str, Any]) -> dict[str, Any]:
    if source.get("environment") != "pre-production":
        raise ValueError("working catalog must remain pre-production")
    if source.get("package_state") != "draft":
        raise ValueError("working catalog must remain draft")
    _require_false(source, "catalog_approved")
    _require_false(source, "mutation_authorized")
    _require_false(source, "production_publish_authorized")

    source_contract = source.get("source_contract") or {}
    if source_contract.get("production_write_authority_granted_by_handoff") is not False:
        raise ValueError("working catalog handoff must not grant production writes")

    products: list[dict[str, Any]] = []
    for item in source.get("working_products") or []:
        product_type = item.get("product_type")
        key = item.get("parent_reference") if product_type == "variable" else item.get("sku")
        if product_type not in {"simple", "variable"} or not isinstance(key, str) or not key.startswith("RCD-"):
            raise ValueError("working catalog contains an unsupported product identity")
        english_name = item.get("english_name")
        english_description = item.get("english_description")
        if not isinstance(english_name, str) or not english_name.strip():
            raise ValueError(f"{key}: English product name is required for preview projection")
        if not isinstance(english_description, str) or not english_description.strip():
            raise ValueError(f"{key}: English description is required for preview projection")

        projected: dict[str, Any] = {
            "key": key,
            "product_type": product_type,
            "english_name": english_name,
            "japanese_name": item.get("japanese_name"),
            "english_description": english_description,
            "japanese_description": item.get("japanese_description"),
            "family": item.get("family"),
            "form": item.get("form"),
            "pickup_allowed": item.get("pickup_allowed") is True,
            "delivery_allowed": item.get("delivery_allowed") is True,
        }

        if product_type == "variable":
            variants = item.get("variants") or []
            if not variants:
                raise ValueError(f"{key}: variable product requires working variants")
            projected_variants = []
            for variant in variants:
                sku = variant.get("sku")
                price = variant.get("price_jpy")
                size = variant.get("size_cm")
                if not isinstance(sku, str) or not sku.startswith("RCD-"):
                    raise ValueError(f"{key}: invalid working variant SKU")
                if not isinstance(price, int) or price <= 0:
                    raise ValueError(f"{sku}: positive working price is required")
                if not isinstance(size, (int, float)) or size <= 0:
                    raise ValueError(f"{sku}: positive size is required")
                projected_variants.append({"size_cm": size, "sku": sku, "price_jpy": price})
            projected["variants"] = projected_variants
            projected["price_jpy"] = min(v["price_jpy"] for v in projected_variants)
            projected["price_mode"] = "from"
        else:
            price = item.get("price_jpy")
            if not isinstance(price, int) or price <= 0:
                raise ValueError(f"{key}: positive working price is required")
            projected["price_jpy"] = price
            projected["price_mode"] = "exact"
            projected["variants"] = []

        products.append(projected)

    if not products:
        raise ValueError("working catalog projection cannot be empty")

    return {
        "schema_version": "1.0",
        "source_fixture": SOURCE.name,
        "preview_only": True,
        "catalog_approved": False,
        "mutation_authorized": False,
        "production_publish_authorized": False,
        "products": products,
    }


def build_projection(source_path: Path = SOURCE) -> dict[str, Any]:
    return build_projection_from_source(json.loads(source_path.read_text(encoding="utf-8")))


def render_module(projection: dict[str, Any]) -> str:
    payload = json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        "// Generated from the bounded Sprint 3 working catalog. Do not edit by hand.\n"
        "// Preview-only projection: no production write, publish, payment, SMS, or inventory authority.\n"
        f"export const workingCatalogPreview = Object.freeze({payload});\n"
        "export default workingCatalogPreview;\n"
    )


def write_projection(output_path: Path = OUTPUT) -> None:
    output_path.write_text(render_module(build_projection()), encoding="utf-8")


def check_projection(output_path: Path = OUTPUT) -> bool:
    return output_path.read_text(encoding="utf-8") == render_module(build_projection())


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate bounded storefront catalog preview data")
    parser.add_argument("--check", action="store_true", help="fail when the committed projection is stale")
    args = parser.parse_args()
    if args.check:
        if not check_projection():
            raise SystemExit("storefront catalog preview projection is stale")
        return 0
    write_projection()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

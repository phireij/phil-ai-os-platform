#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from phil_ai_os_woocommerce.working_catalog_draft_plan import build_working_catalog_draft_plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a non-authorizing WooCommerce draft plan from a working catalog subset.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        plan = build_working_catalog_draft_plan(payload)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"PHIL_AI_OS_WORKING_CATALOG_DRAFT_PLAN_FAILED: {exc}", file=sys.stderr)
        return 2

    rendered_payload = {
        "products": [
            {
                "key": product.key,
                "product_type": product.product_type,
                "status": product.status,
                "catalog_visibility": product.catalog_visibility,
                "english_name": product.english_name,
                "japanese_name": product.japanese_name,
                "price_jpy": product.price_jpy,
                "variations": [
                    {"sku": item.sku, "price_jpy": item.price_jpy, "size_cm": item.size_cm}
                    for item in product.variations
                ],
                "unresolved_fields": list(product.unresolved_fields),
            }
            for product in plan.products
        ],
        "network_call_performed": False,
        "mutation_authorized": False,
        "production_publish_authorized": False,
    }
    rendered = json.dumps(rendered_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    print(
        "PHIL_AI_OS_WORKING_CATALOG_DRAFT_PLAN_GREEN "
        f"product_count={len(plan.products)} network_call=false mutation_authorized=false production_publish_authorized=false",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

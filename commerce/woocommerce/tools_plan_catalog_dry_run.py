#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from phil_ai_os_woocommerce.catalog_dry_run import plan_catalog_product_reconciliation
from phil_ai_os_woocommerce.models import ContractValidationError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a side-effect-free WooCommerce product reconciliation plan from "
            "an approved catalog intake file and a caller-supplied read-only remote snapshot."
        )
    )
    parser.add_argument("--intake", required=True, type=Path, help="Catalog intake JSON path")
    parser.add_argument(
        "--remote-snapshot",
        required=True,
        type=Path,
        help="Read-only WooCommerce product snapshot JSON path (array or {products: [...]})",
    )
    parser.add_argument("--locale", choices=("en", "ja"), default="en")
    parser.add_argument("--output", type=Path, help="Optional output JSON path")
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    try:
        intake = load_json(args.intake)
        remote_payload = load_json(args.remote_snapshot)
        if isinstance(remote_payload, list):
            remote_products = remote_payload
        elif isinstance(remote_payload, dict) and isinstance(remote_payload.get("products"), list):
            remote_products = remote_payload["products"]
        else:
            raise ContractValidationError(
                "remote snapshot must be a JSON array or an object with a products array"
            )

        plan = plan_catalog_product_reconciliation(
            intake,
            remote_products,
            locale=args.locale,
        ).as_dict()
    except (OSError, json.JSONDecodeError, ContractValidationError, TypeError, ValueError) as exc:
        print(f"PHIL_AI_OS_CATALOG_DRY_RUN_FAILED: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    print(
        "PHIL_AI_OS_CATALOG_DRY_RUN_GREEN "
        f"create={plan['counts']['create']} update={plan['counts']['update']} "
        f"noop={plan['counts']['noop']} network_call=false mutation_authorized=false",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

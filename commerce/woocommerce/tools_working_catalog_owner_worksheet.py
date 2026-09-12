#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from phil_ai_os_woocommerce.working_catalog_owner_worksheet import (
    build_working_catalog_owner_worksheet,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a source-backed, owner-editable catalog CSV with explicit parent/variation SKUs. "
            "The worksheet is non-authorizing and performs no network calls."
        )
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--requirements-output",
        type=Path,
        help="Optional JSON file containing unresolved global requirements and authority flags.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        worksheet = build_working_catalog_owner_worksheet(payload)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=worksheet.columns, extrasaction="raise")
            writer.writeheader()
            writer.writerows(worksheet.rows)

        if args.requirements_output:
            args.requirements_output.parent.mkdir(parents=True, exist_ok=True)
            args.requirements_output.write_text(
                json.dumps(
                    {
                        "global_requirements": list(worksheet.global_requirements),
                        "network_call_performed": worksheet.network_call_performed,
                        "mutation_authorized": worksheet.mutation_authorized,
                        "production_publish_authorized": worksheet.production_publish_authorized,
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"PHIL_AI_OS_CATALOG_OWNER_WORKSHEET_FAILED: {exc}", file=sys.stderr)
        return 2

    print(
        "PHIL_AI_OS_CATALOG_OWNER_WORKSHEET_GREEN "
        f"rows={len(worksheet.rows)} global_requirements={len(worksheet.global_requirements)} "
        "network_call=false mutation_authorized=false production_publish_authorized=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from phil_ai_os_woocommerce.working_catalog_owner_worksheet_intake import (
    parse_owner_worksheet_csv,
    review_owner_worksheet_intake,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review an edited Ruby catalog owner worksheet against the canonical source-backed subset. "
            "The review emits proposals only and never applies catalog or production changes."
        )
    )
    parser.add_argument("--source", required=True, type=Path, help="Canonical working catalog subset JSON")
    parser.add_argument("--worksheet", required=True, type=Path, help="Completed owner worksheet CSV")
    parser.add_argument("--output", type=Path, help="Optional JSON review output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        source_payload = json.loads(args.source.read_text(encoding="utf-8"))
        worksheet_text = args.worksheet.read_text(encoding="utf-8-sig")
        rows = parse_owner_worksheet_csv(worksheet_text)
        review = review_owner_worksheet_intake(source_payload, rows)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"PHIL_AI_OS_CATALOG_OWNER_WORKSHEET_INTAKE_FAILED: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(review.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    if not review.structurally_valid:
        print(
            "PHIL_AI_OS_CATALOG_OWNER_WORKSHEET_INTAKE_BLOCKED "
            f"blockers={len(review.blockers)} changes={len(review.proposed_changes)} "
            "network_call=false mutation_authorized=false production_publish_authorized=false "
            "automatic_apply_authorized=false",
            file=sys.stderr,
        )
        return 2

    print(
        "PHIL_AI_OS_CATALOG_OWNER_WORKSHEET_INTAKE_GREEN "
        f"rows={review.row_count} changes={len(review.proposed_changes)} "
        "ready_for_owner_fact_review=true network_call=false mutation_authorized=false "
        "production_publish_authorized=false automatic_apply_authorized=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

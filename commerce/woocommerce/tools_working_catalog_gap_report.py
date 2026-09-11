#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from phil_ai_os_woocommerce.working_catalog_gap_report import build_working_catalog_gap_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a side-effect-free readiness gap report for a Ruby working catalog subset. "
            "This command never grants production readiness or mutation authority."
        )
    )
    parser.add_argument("--input", required=True, type=Path, help="Working catalog subset JSON path")
    parser.add_argument("--output", type=Path, help="Optional output JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        report = build_working_catalog_gap_report(payload)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"PHIL_AI_OS_WORKING_CATALOG_GAP_REPORT_FAILED: {exc}", file=sys.stderr)
        return 2

    rendered_payload = {
        "production_ready": report.production_ready,
        "global_gaps": list(report.global_gaps),
        "product_gaps": [
            {"key": item.key, "missing": list(item.missing)}
            for item in report.product_gaps
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
        "PHIL_AI_OS_WORKING_CATALOG_GAP_REPORT_GREEN "
        f"production_ready={str(report.production_ready).lower()} "
        f"global_gaps={len(report.global_gaps)} product_count={len(report.product_gaps)} "
        "network_call=false mutation_authorized=false production_publish_authorized=false",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from phil_ai_os_woocommerce.working_catalog_category_candidates import (
    build_working_catalog_category_candidate_packet,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a side-effect-free category candidate packet from owner-supplied working-catalog labels. "
            "This command never invents category mappings or grants production authority."
        )
    )
    parser.add_argument("--input", required=True, type=Path, help="Working catalog subset JSON path")
    parser.add_argument("--output", type=Path, help="Optional output JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        packet = build_working_catalog_category_candidate_packet(payload)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"PHIL_AI_OS_WORKING_CATALOG_CATEGORY_CANDIDATES_FAILED: {exc}", file=sys.stderr)
        return 2

    rendered_payload = {
        "ready_for_category_mapping_approval": packet.ready_for_category_mapping_approval,
        "candidates": [
            {
                "source_label": candidate.source_label,
                "product_keys": list(candidate.product_keys),
                "english_name": candidate.english_name,
                "japanese_name": candidate.japanese_name,
                "english_slug": candidate.english_slug,
                "japanese_slug": candidate.japanese_slug,
                "mapping_approved": candidate.mapping_approved,
            }
            for candidate in packet.candidates
        ],
        "blockers": list(packet.blockers),
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
        "PHIL_AI_OS_WORKING_CATALOG_CATEGORY_CANDIDATES_GREEN "
        f"candidate_count={len(packet.candidates)} blocker_count={len(packet.blockers)} "
        "network_call=false mutation_authorized=false production_publish_authorized=false",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

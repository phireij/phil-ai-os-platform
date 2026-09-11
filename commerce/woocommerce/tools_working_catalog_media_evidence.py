#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from phil_ai_os_woocommerce.working_catalog_media_evidence import (
    build_working_catalog_media_evidence_packet,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a side-effect-free media evidence packet from a Ruby working catalog subset. "
            "This command never invents media references or grants production authority."
        )
    )
    parser.add_argument("--input", required=True, type=Path, help="Working catalog subset JSON path")
    parser.add_argument("--output", type=Path, help="Optional output JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        packet = build_working_catalog_media_evidence_packet(payload)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"PHIL_AI_OS_WORKING_CATALOG_MEDIA_EVIDENCE_FAILED: {exc}", file=sys.stderr)
        return 2

    rendered_payload = {
        "ready_for_media_ingestion_review": packet.ready_for_media_ingestion_review,
        "items": [
            {
                "product_key": item.product_key,
                "source_state": item.source_state,
                "verified_media_reference": item.verified_media_reference,
                "primary_media_confirmed": item.primary_media_confirmed,
            }
            for item in packet.items
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
        "PHIL_AI_OS_WORKING_CATALOG_MEDIA_EVIDENCE_GREEN "
        f"item_count={len(packet.items)} blocker_count={len(packet.blockers)} "
        "network_call=false mutation_authorized=false production_publish_authorized=false",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

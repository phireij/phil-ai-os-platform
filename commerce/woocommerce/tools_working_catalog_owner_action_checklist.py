#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from phil_ai_os_woocommerce.working_catalog_owner_action_checklist import (
    render_working_catalog_owner_action_checklist,
)
from phil_ai_os_woocommerce.working_catalog_owner_action_packet import (
    build_working_catalog_owner_action_packet,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render the remaining working-catalog owner/operational actions as a human-readable "
            "Markdown checklist without supplying decisions or granting production authority."
        )
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        packet = build_working_catalog_owner_action_packet(payload)
        rendered = render_working_catalog_owner_action_checklist(payload)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"PHIL_AI_OS_CATALOG_OWNER_ACTION_CHECKLIST_FAILED: {exc}", file=sys.stderr)
        return 2

    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    print(
        "PHIL_AI_OS_CATALOG_OWNER_ACTION_CHECKLIST_GREEN "
        f"action_count={len(packet.actions)} production_ready={str(packet.production_ready).lower()} "
        "network_call=false mutation_authorized=false production_publish_authorized=false",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

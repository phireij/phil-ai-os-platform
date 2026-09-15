#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phil_ai_os_woocommerce.working_catalog_owner_decision_brief import (
    build_working_catalog_owner_decision_brief,
    render_working_catalog_owner_decision_brief,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a non-authorizing CEO decision brief from the working catalog owner action packet."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--proposals", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        catalog = json.loads(args.input.read_text(encoding="utf-8"))
        proposals = json.loads(args.proposals.read_text(encoding="utf-8"))
        brief = build_working_catalog_owner_decision_brief(catalog, proposals)
        rendered = render_working_catalog_owner_decision_brief(brief)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"PHIL_AI_OS_CATALOG_OWNER_DECISION_BRIEF_FAILED: {exc}", file=sys.stderr)
        return 2

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)

    print(
        "PHIL_AI_OS_CATALOG_OWNER_DECISION_BRIEF_GREEN "
        f"owner_decisions={len(brief.owner_decisions)} "
        f"draft_assisted={len(brief.japanese_draft_action_keys)} "
        f"post_decision_records={len(brief.post_decision_records)} "
        f"operational_evidence={len(brief.operational_evidence)} "
        f"deferred_authority={len(brief.deferred_authority_gates)} "
        f"needs_review={len(brief.needs_review)} "
        "network_call=false mutation_authorized=false production_publish_authorized=false",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

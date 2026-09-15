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

from phil_ai_os_woocommerce.working_catalog_owner_draft_assistance import (
    build_working_catalog_owner_draft_assistance,
    render_working_catalog_owner_draft_assistance_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render proposal-only Japanese copy draft assistance for the working catalog."
    )
    parser.add_argument("--input", required=True, help="Source-backed working catalog JSON")
    parser.add_argument("--proposals", required=True, help="Proposal-only Japanese copy JSON")
    parser.add_argument("--output", help="Optional Markdown output path; otherwise stdout")
    args = parser.parse_args()

    try:
        catalog = json.loads(Path(args.input).read_text(encoding="utf-8"))
        proposals = json.loads(Path(args.proposals).read_text(encoding="utf-8"))
        assistance = build_working_catalog_owner_draft_assistance(catalog, proposals)
        rendered = render_working_catalog_owner_draft_assistance_markdown(assistance)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        print(
            "PHIL_AI_OS_CATALOG_OWNER_DRAFT_ASSISTANCE_GREEN "
            f"drafts={len(assistance.drafts)} owner_approved=false canonical_apply_authorized=false "
            "network_call=false mutation_authorized=false production_publish_authorized=false",
            file=sys.stderr,
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"PHIL_AI_OS_CATALOG_OWNER_DRAFT_ASSISTANCE_FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

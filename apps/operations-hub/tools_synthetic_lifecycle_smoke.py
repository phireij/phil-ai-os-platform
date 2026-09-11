#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.normalizer import SUPPORTED_SOURCES  # noqa: E402
from operations_hub.synthetic_lifecycle import run_synthetic_multichannel_lifecycle  # noqa: E402


def main() -> int:
    fixtures = {
        source: json.loads((ROOT / "fixtures" / f"{source}.json").read_text(encoding="utf-8"))
        for source in SUPPORTED_SOURCES
    }
    evidence = run_synthetic_multichannel_lifecycle(fixtures)

    if any(
        evidence[field]
        for field in (
            "network_call_performed",
            "external_dispatch_performed",
            "order_mutation_performed",
            "payment_performed",
            "inventory_mutation_performed",
            "production_authority_changed",
        )
    ):
        raise SystemExit("PHIL_AI_OS_SPRINT_5_MULTICHANNEL_SYNTHETIC_FAILED: authority expanded")

    print(
        "PHIL_AI_OS_SPRINT_5_MULTICHANNEL_SYNTHETIC_GREEN "
        f"sources={','.join(evidence['sources'])} "
        f"accepted={evidence['queue']['total_events']} "
        f"duplicates_blocked={evidence['queue']['duplicate_events']} "
        f"review_routed={evidence['queue']['review_required']} "
        "network_call=false external_dispatch=false order_mutation=false "
        "payment=false inventory_mutation=false production_authority=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

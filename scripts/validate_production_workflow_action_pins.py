#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = [
    ROOT / ".github/workflows/commerce-woocommerce-production-readonly-preflight.yml",
    ROOT / ".github/workflows/commerce-woocommerce-production-readonly-catalog-snapshot.yml",
    ROOT / ".github/workflows/commerce-twilio-production-readonly-preflight.yml",
]
PINNED = re.compile(r"^\s*-\s+uses:\s+[^@\s]+@[0-9a-f]{40}(?:\s+#.*)?$", re.MULTILINE)
USES = re.compile(r"^\s*-\s+uses:\s+.+$", re.MULTILINE)


def main() -> int:
    failures: list[str] = []
    for path in WORKFLOWS:
        text = path.read_text(encoding="utf-8")
        uses = USES.findall(text)
        if not uses:
            failures.append(f"{path}: no action references found")
            continue
        for line in uses:
            if not PINNED.match(line):
                failures.append(f"{path}: floating or invalid action reference: {line.strip()}")
        if "permissions:\n  contents: read" not in text:
            failures.append(f"{path}: contents permission is not explicitly read-only")

    if failures:
        for item in failures:
            print(f"PHIL_AI_OS_PRODUCTION_WORKFLOW_PIN_VALIDATION_FAILED: {item}")
        return 1

    print("PHIL_AI_OS_PRODUCTION_WORKFLOW_ACTION_PINS_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

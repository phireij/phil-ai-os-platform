#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub import InMemoryDeduplicator, SUPPORTED_SOURCES, evaluate_governance, normalize_channel_event  # noqa: E402


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_5_OPERATIONS_VALIDATION_FAILED: {message}")


def main() -> None:
    raw_schema = json.loads((REPO / "contracts/operations/raw-channel-event.schema.json").read_text(encoding="utf-8"))
    normalized_schema = json.loads((REPO / "contracts/operations/business-event.schema.json").read_text(encoding="utf-8"))
    governance_schema = json.loads((REPO / "contracts/operations/governance-evaluation.schema.json").read_text(encoding="utf-8"))

    raw_sources = tuple(raw_schema["properties"]["source"]["enum"])
    normalized_sources = tuple(normalized_schema["properties"]["source"]["enum"])
    governance_sources = tuple(governance_schema["properties"]["source"]["enum"])
    if raw_sources != SUPPORTED_SOURCES or normalized_sources != SUPPORTED_SOURCES or governance_sources != SUPPORTED_SOURCES:
        fail("source allowlists must match runtime exactly")
    if normalized_schema["properties"]["mutation_authorized"].get("const") is not False:
        fail("normalized contract must keep mutation_authorized=false")

    for field in ("execution_authorized", "channel_reply_authorized", "mutation_authorized"):
        if governance_schema["properties"][field].get("const") is not False:
            fail(f"governance contract must keep {field}=false")
    if governance_schema["properties"]["authority_effect"].get("const") != "none":
        fail("governance contract authority_effect must remain none")

    dedupe = InMemoryDeduplicator()
    normalized = []
    evaluations = []
    for source in SUPPORTED_SOURCES:
        fixture_path = ROOT / "fixtures" / f"{source}.json"
        if not fixture_path.is_file():
            fail(f"missing fixture for {source}")
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        if payload.get("fixture_only") is not True or payload.get("source") != source:
            fail(f"{source} fixture boundary invalid")
        event = normalize_channel_event(payload)
        if event["mutation_authorized"] is not False:
            fail(f"{source} gained mutation authority")
        first = dedupe.accept(event)
        second = dedupe.accept(event)
        if not first.accepted or not second.duplicate:
            fail(f"{source} idempotency behavior invalid")
        evaluation = evaluate_governance(event)
        if evaluation["authority_effect"] != "none" or any(
            evaluation[field] is not False
            for field in ("execution_authorized", "channel_reply_authorized", "mutation_authorized")
        ):
            fail(f"{source} governance evaluation gained authority")
        normalized.append(event)
        evaluations.append(evaluation)

    review_sources = {event["source"] for event in normalized if event["review_required"]}
    approval_sources = {item["source"] for item in evaluations if item["approval_required"]}
    if not {"whatsapp", "google_business"}.issubset(review_sources):
        fail("sensitive/public-review fixtures must route to review")
    if not {"whatsapp", "google_business"}.issubset(approval_sources):
        fail("sensitive/public-review fixtures must require governance approval")

    sample = json.loads((REPO / "contracts/operations/fixtures/order-intent.sample.json").read_text(encoding="utf-8"))
    required = set(normalized_schema["required"])
    if not required.issubset(sample):
        fail("operations sample is missing normalized required fields")
    if sample.get("mutation_authorized") is not False:
        fail("operations sample must be non-authorizing")

    scan_paths = [ROOT, REPO / "contracts/operations"]
    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for base in scan_paths
        for path in base.rglob("*")
        if path.is_file() and path.suffix in {".py", ".json", ".md", ".yml", ".yaml"}
    )
    forbidden = {
        "Meta long-lived token": r"\bEAA[A-Za-z0-9]{24,}\b",
        "WhatsApp bearer token": r"\bEA[A-Za-z0-9]{40,}\b",
        "Google API key": r"\bAIza[A-Za-z0-9_-]{30,}\b",
        "authorizing mutation flag": r"mutation_authorized\s*[\":=]+\s*true",
        "authorizing reply flag": r"channel_reply_authorized\s*[\":=]+\s*true",
        "authorizing execution flag": r"execution_authorized\s*[\":=]+\s*true",
    }
    for label, pattern in forbidden.items():
        if re.search(pattern, combined, flags=re.IGNORECASE):
            fail(f"forbidden {label} found")

    print(
        "PHIL_AI_OS_SPRINT_5_OPERATIONS_VALIDATION_GREEN "
        f"sources={len(normalized)} review_routed={len(review_sources)} approval_routed={len(approval_sources)}"
    )
    print("PHIL_AI_OS_SPRINT_5_GOVERNANCE_BRIDGE_GREEN authority_effect=none")


if __name__ == "__main__":
    main()

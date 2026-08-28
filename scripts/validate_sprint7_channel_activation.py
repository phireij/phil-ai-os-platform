#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "ops/readiness/sprint7-channel-activation-readiness.json"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_7_CHANNEL_READINESS_FAILED: {message}")


def main() -> None:
    data = json.loads(READINESS.read_text(encoding="utf-8"))
    baseline = data["authority_baseline"]
    expected = {
        "autonomy": "A0",
        "task_class_allowlist": ["general"],
        "assigned_agent": "hermes",
        "specialists_enabled": False,
        "live_channel_connectivity_authorized": False,
        "outbound_reply_authorized": False,
        "customer_account_mutation_authorized": False,
    }
    for key, value in expected.items():
        if baseline.get(key) != value:
            fail(f"authority baseline drift: {key}={baseline.get(key)!r}")

    required_channels = {"facebook", "instagram", "telegram", "whatsapp", "google_business"}
    channels = {item["channel"]: item for item in data.get("channels", [])}
    if set(channels) != required_channels:
        fail(f"channel set drift: {sorted(channels)}")

    for name, channel in channels.items():
        for flag in (
            "credential_introduced",
            "live_connectivity_authorized",
            "inbound_activation_authorized",
            "outbound_reply_authorized",
        ):
            if channel.get(flag) is not False:
                fail(f"{name} authority drift: {flag}")
        if channel.get("write_scope_separate_gate") is not True:
            fail(f"{name} write scope must remain separately gated")
        requirements = channel.get("activation_requirements") or []
        if len(requirements) < 4:
            fail(f"{name} activation requirements incomplete")
        if "rollback_disable_path" not in requirements:
            fail(f"{name} rollback/disable path missing")

    telegram = channels["telegram"]
    if telegram.get("identity_state") != "existing_control_plane_approval_channel_is_not_operations_authority":
        fail("Telegram control-plane/Operations authority separation drift")

    google = channels["google_business"]
    if "verify_current_google_business_capability_and_permissions_at_activation_time" not in google["activation_requirements"]:
        fail("Google Business current-capability verification requirement missing")

    for rel in data.get("evidence", []):
        if not (ROOT / rel).is_file():
            fail(f"missing channel evidence file: {rel}")

    sprint5 = (ROOT / "docs/SPRINT_5_FORMAL_CLOSURE_2026-08-28.md").read_text(encoding="utf-8")
    required_evidence = (
        "Facebook, Instagram, Telegram, WhatsApp and Google Business",
        "hard-false execution/reply/mutation authority",
        "mock-only provider adapter interfaces",
        "live Facebook/Instagram/Telegram/WhatsApp/Google Business credentials or connectivity",
    )
    for phrase in required_evidence:
        if phrase not in sprint5:
            fail(f"Sprint 5 channel evidence missing: {phrase}")

    runbook = (ROOT / "docs/SPRINT_7_CHANNEL_ACTIVATION_RUNBOOKS_2026-08-28.md").read_text(encoding="utf-8")
    if "PHIL_AI_OS_SPRINT_7_CHANNEL_RUNBOOKS_READY_NOT_AUTHORIZED" not in runbook:
        fail("channel runbook marker missing")
    if "does not grant Operations Hub Telegram channel authority" not in runbook:
        fail("Telegram authority separation statement missing")

    print("PHIL_AI_OS_SPRINT_7_CHANNEL_READINESS_GREEN channels=5 live_connectivity=false outbound_reply=false")
    print("PHIL_AI_OS_SPRINT_7_CHANNEL_AUTHORITY_BOUNDARY_GREEN autonomy=A0 task_class=general assigned_agent=hermes")


if __name__ == "__main__":
    main()

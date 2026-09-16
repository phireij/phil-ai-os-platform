#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "ops" / "readiness" / "sprint7-channel-activation-readiness.json"
OUT = ROOT / "apps" / "operations-hub" / "mission-control" / "channel-readiness.json"
EXPECTED_CHANNELS = {"facebook", "instagram", "telegram", "whatsapp", "google_business"}


def build_projection() -> dict:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    scope = source.get("ceo_controlled_scope") or {}
    if scope.get("customer_channel_activation_and_replies_authorized") is not True:
        raise SystemExit("PHIL_AI_OS_MISSION_CONTROL_CHANNEL_READINESS_BLOCKED controlled_scope_missing=true")
    if scope.get("overrides_channel_preflight_or_evidence") is not False or scope.get("automatic_execution_authorized") is not False:
        raise SystemExit("PHIL_AI_OS_MISSION_CONTROL_CHANNEL_READINESS_BLOCKED controlled_scope_expanded=true")
    baseline = source.get("authority_baseline") or {}
    expected_baseline = {
        "autonomy": "A0",
        "task_class_allowlist": ["general"],
        "assigned_agent": "hermes",
        "specialists_enabled": False,
        "live_channel_connectivity_authorized": False,
        "outbound_reply_authorized": False,
        "customer_account_mutation_authorized": False,
    }
    for key, expected in expected_baseline.items():
        if baseline.get(key) != expected:
            raise SystemExit(f"PHIL_AI_OS_MISSION_CONTROL_CHANNEL_READINESS_BLOCKED baseline_drift={key}")

    channels = source.get("channels") or []
    by_name = {item.get("channel"): item for item in channels if isinstance(item, dict)}
    if set(by_name) != EXPECTED_CHANNELS:
        raise SystemExit("PHIL_AI_OS_MISSION_CONTROL_CHANNEL_READINESS_BLOCKED channel_set_drift=true")

    projected = []
    for name in sorted(EXPECTED_CHANNELS):
        item = by_name[name]
        for flag in (
            "credential_introduced",
            "live_connectivity_authorized",
            "inbound_activation_authorized",
            "outbound_reply_authorized",
        ):
            if item.get(flag) is not False:
                raise SystemExit(f"PHIL_AI_OS_MISSION_CONTROL_CHANNEL_READINESS_BLOCKED {name}_{flag}=true")
        if item.get("write_scope_separate_gate") is not True:
            raise SystemExit(f"PHIL_AI_OS_MISSION_CONTROL_CHANNEL_READINESS_BLOCKED {name}_write_gate=false")
        if item.get("controlled_scope_authorized") is not True:
            raise SystemExit(f"PHIL_AI_OS_MISSION_CONTROL_CHANNEL_READINESS_BLOCKED {name}_controlled_scope_missing=true")
        projected.append(
            {
                "channel": name,
                "identity_state": str(item.get("identity_state") or "unknown"),
                "credential_introduced": False,
                "live_connectivity_authorized": False,
                "inbound_activation_authorized": False,
                "outbound_reply_authorized": False,
                "controlled_scope_authorized": True,
                "write_scope_separate_gate": True,
            }
        )

    return {
        "schema": "phil-ai-os-mission-control-channel-readiness",
        "version": 1,
        "status": "read_only",
        "source_version": source.get("version"),
        "controlled_scope_authorized": True,
        "controlled_scope_overrides_preflight": False,
        "autonomy_level": "A0",
        "execution_task_class": "general",
        "assigned_agent": "hermes",
        "specialists_enabled": False,
        "channel_count": len(projected),
        "channels": projected,
        "live_channel_connectivity_authorized": False,
        "outbound_reply_authorized": False,
        "customer_account_mutation_authorized": False,
        "authority_effect": "none",
    }


def render() -> str:
    return json.dumps(build_projection(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate privacy-safe Mission Control channel readiness")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    generated = render()
    if args.check:
        if OUT.read_text(encoding="utf-8") != generated:
            raise SystemExit("PHIL_AI_OS_MISSION_CONTROL_CHANNEL_READINESS_DRIFT")
        print("PHIL_AI_OS_MISSION_CONTROL_CHANNEL_READINESS_GREEN channels=5 live_connectivity=false outbound_reply=false")
        return
    OUT.write_text(generated, encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

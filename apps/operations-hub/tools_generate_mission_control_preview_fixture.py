#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from operations_hub import build_mission_control_lifecycle_projection  # noqa: E402

OUT = ROOT / "mission-control" / "fixture.json"


def build_source_models() -> tuple[dict, dict]:
    operations_dashboard = {
        "status": "read_only",
        "channels": {"total_events": 5},
        "tasks": {
            "task_count": 5,
            "duplicate_tasks": 1,
            "awaiting_approval": 2,
            "ready_for_operator_review": 3,
            "source_counts": {"facebook": 2, "instagram": 1, "telegram": 1, "whatsapp": 1},
            "task_type_counts": {"customer_message_review": 2, "order_intent_review": 3},
        },
        "orders": {"pending_staff_review": 1},
        "quotes": {"pending_approval": 1},
        "owner_review": {"pending_packets": 2},
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "quote_authorized": False,
        "customer_notification_authorized": False,
        "woo_commerce_mutation_authorized": False,
        "order_creation_authorized": False,
        "payment_execution_authorized": False,
        "sms_send_authorized": False,
        "inventory_mutation_authorized": False,
        "production_publish_authorized": False,
        "mutation_authorized": False,
    }

    items = []
    lifecycle_defs = (
        (
            "mc-demo-facebook-order-001",
            (("normalized", "accepted"), ("governance", "review_only"), ("planned", "simulation_ready"), ("simulated", "operator_review_required")),
        ),
        (
            "mc-demo-whatsapp-issue-001",
            (("normalized", "accepted"), ("planned", "simulation_ready"), ("simulated", "approval_boundary_verified"), ("governance", "awaiting_approval")),
        ),
    )
    for lifecycle_id, events in lifecycle_defs:
        for sequence, (stage, outcome) in enumerate(events, start=1):
            items.append(
                {
                    "lifecycle_correlation_id": lifecycle_id,
                    "sequence": sequence,
                    "stage": stage,
                    "outcome": outcome,
                    "simulated": True,
                    "execution_authorized": False,
                    "channel_reply_authorized": False,
                    "mutation_authorized": False,
                    "authority_effect": "none",
                }
            )

    automation_audit = {
        "read_only": True,
        "total_events": len(items),
        "by_stage": {"normalized": 2, "governance": 2, "planned": 2, "simulated": 2},
        "items": items,
        "authority_effect": "none",
    }
    return operations_dashboard, automation_audit


def render() -> str:
    dashboard, audit = build_source_models()
    projection = build_mission_control_lifecycle_projection(dashboard, audit)
    return json.dumps(projection, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the bounded Mission Control read-only preview fixture")
    parser.add_argument("--check", action="store_true", help="Fail if committed fixture differs from generated projection")
    args = parser.parse_args()

    generated = render()
    if args.check:
        current = OUT.read_text(encoding="utf-8")
        if current != generated:
            raise SystemExit("PHIL_AI_OS_MISSION_CONTROL_FIXTURE_DRIFT: regenerate fixture before merging")
        print("PHIL_AI_OS_MISSION_CONTROL_FIXTURE_GREEN generated_from_projection=true task_composition=read_only authority_effect=none")
        return

    OUT.write_text(generated, encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

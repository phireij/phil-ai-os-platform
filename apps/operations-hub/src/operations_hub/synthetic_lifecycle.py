from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from .governance import evaluate_governance
from .normalizer import SUPPORTED_SOURCES, normalize_channel_event
from .queue import OperationsQueue


class SyntheticLifecycleError(ValueError):
    pass


def run_synthetic_multichannel_lifecycle(
    fixtures_by_source: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Compose bounded Operations Hub ingestion, dedupe, queue, and governance evidence.

    This helper is fixture-only. It performs no network call, channel reply, payment,
    order/inventory mutation, or production action. It exists to prove that the
    isolated Sprint 5 contracts remain coherent when all supported channels pass
    through one lifecycle.
    """

    if not isinstance(fixtures_by_source, Mapping):
        raise SyntheticLifecycleError("fixtures_by_source must be a mapping")

    expected = set(SUPPORTED_SOURCES)
    actual = set(fixtures_by_source)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise SyntheticLifecycleError(
            f"synthetic lifecycle requires the exact supported source set; missing={missing} extra={extra}"
        )

    queue = OperationsQueue()
    channel_results: list[dict[str, Any]] = []

    for source in SUPPORTED_SOURCES:
        raw = fixtures_by_source[source]
        if not isinstance(raw, Mapping):
            raise SyntheticLifecycleError(f"{source} fixture must be an object")
        payload = copy.deepcopy(dict(raw))
        if payload.get("fixture_only") is not True:
            raise SyntheticLifecycleError(f"{source} fixture must remain fixture_only")
        if payload.get("source") != source:
            raise SyntheticLifecycleError(f"{source} fixture source mismatch")

        event = normalize_channel_event(payload)
        first = queue.ingest(event)
        duplicate = queue.ingest(event)
        if not first.get("accepted") or first.get("duplicate"):
            raise SyntheticLifecycleError(f"{source} first queue ingest must be accepted")
        if duplicate.get("accepted") or not duplicate.get("duplicate"):
            raise SyntheticLifecycleError(f"{source} duplicate queue ingest must fail closed")

        governance = evaluate_governance(event)
        if governance.get("authority_effect") != "none":
            raise SyntheticLifecycleError(f"{source} governance changed authority")
        for field in ("execution_authorized", "channel_reply_authorized", "mutation_authorized"):
            if governance.get(field) is not False:
                raise SyntheticLifecycleError(f"{source} governance authorized {field}")

        channel_results.append(
            {
                "source": source,
                "kind": event["kind"],
                "normalized_intent": event["normalized_intent"],
                "review_required": event["review_required"],
                "approval_required": governance["approval_required"],
                "risk_level": governance["risk_level"],
                "first_ingest_accepted": True,
                "duplicate_rejected": True,
                "execution_authorized": False,
                "channel_reply_authorized": False,
                "mutation_authorized": False,
                "authority_effect": "none",
            }
        )

    queue_view = queue.read_model()
    if queue_view["total_events"] != len(SUPPORTED_SOURCES):
        raise SyntheticLifecycleError("queue must contain one accepted event per supported source")
    if queue_view["duplicate_events"] != len(SUPPORTED_SOURCES):
        raise SyntheticLifecycleError("queue must record one rejected duplicate per supported source")
    if queue_view.get("mutation_authorized") is not False:
        raise SyntheticLifecycleError("queue gained mutation authority")

    return {
        "smoke": "sprint5_operations_multichannel_lifecycle_synthetic",
        "fixture_only": True,
        "sources": list(SUPPORTED_SOURCES),
        "channels": channel_results,
        "queue": queue_view,
        "network_call_performed": False,
        "external_dispatch_performed": False,
        "order_mutation_performed": False,
        "payment_performed": False,
        "inventory_mutation_performed": False,
        "production_authority_changed": False,
    }

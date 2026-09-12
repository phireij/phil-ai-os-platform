#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "apps/operations-hub/src"))

from operations_hub import (  # noqa: E402
    OrderReviewQueue,
    build_order_quote_approval_request,
    build_order_quote_draft,
    build_order_quote_preparation,
    build_order_review_decision_proposal,
    normalize_order_intake_handoff,
)


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_7_CX_OPS_ORDER_LIFECYCLE_FAILED: {message}")


def assert_no_authority_expansion(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.casefold().replace("_", "")
            if normalized.endswith("authorized") and child is not False:
                fail(f"authority expansion at {path}.{key}")
            if normalized in {"networkcallperformed", "fileuploadperformed", "filecontentpersisted"} and child is not False:
                fail(f"side-effect flag changed at {path}.{key}")
            assert_no_authority_expansion(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_authority_expansion(child, f"{path}[{index}]")


def main() -> None:
    emitter = REPO / "apps/customer-experience/tools_emit_order_intake_review_handoff.mjs"
    completed = subprocess.run(
        ["node", str(emitter)],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    )
    handoff = json.loads(completed.stdout)

    if handoff.get("schema") != "rubys-order-intake-review-handoff":
        fail("CX emitted an unexpected handoff schema")
    if handoff.get("state") != "prepared_for_staff_review":
        fail("CX handoff did not remain prepared_for_staff_review")
    images = handoff.get("request", {}).get("customization", {}).get("referenceImages")
    if images != [{"name": "synthetic-reference.jpg", "type": "image/jpeg"}]:
        fail("reference-image metadata boundary changed")
    assert_no_authority_expansion(handoff, "cx_handoff")

    normalized = normalize_order_intake_handoff(handoff)
    correlation_id = normalized["lifecycle_correlation_id"]
    if normalized.get("review_state") != "pending_staff_review":
        fail("Operations Hub did not route handoff to pending staff review")
    assert_no_authority_expansion(normalized, "normalized")

    queue = OrderReviewQueue()
    first = queue.ingest_handoff(handoff)
    duplicate = queue.ingest_handoff(handoff)
    if first.get("accepted") is not True or duplicate.get("duplicate") is not True:
        fail("order handoff idempotency boundary changed")
    queue_model = queue.read_model()
    if queue_model.get("pending_review") != 1 or queue_model.get("duplicate_handoffs") != 1:
        fail("order review queue counts are invalid")

    review = queue.review_detail(correlation_id)
    if review is None:
        fail("review detail missing")
    proposal = build_order_review_decision_proposal(
        review,
        "accept_for_quote_review",
        "staff:synthetic-integration",
        "Synthetic integration fixture only.",
    )
    preparation = build_order_quote_preparation(review, proposal)
    draft = build_order_quote_draft(
        preparation,
        quote_amount=5000,
        shipping_amount=0,
        total_amount=5000,
        prepared_by="staff:synthetic-integration",
        note="Synthetic JPY values for integration validation only; not catalog facts.",
    )
    approval_request = build_order_quote_approval_request(
        draft,
        requested_by="staff:synthetic-integration",
        reason="Synthetic approval-gate validation only.",
    )

    lifecycle = [normalized, review, proposal, preparation, draft, approval_request]
    for index, stage in enumerate(lifecycle):
        if stage.get("lifecycle_correlation_id") != correlation_id:
            fail(f"correlation continuity failed at lifecycle stage {index}")
        assert_no_authority_expansion(stage, f"lifecycle[{index}]")

    if approval_request.get("state") != "approval_requested":
        fail("quote approval request did not stop at approval_requested")
    if approval_request.get("approval", {}).get("decision") is not None:
        fail("synthetic lifecycle unexpectedly made an approval decision")

    print(
        "PHIL_AI_OS_SPRINT_7_CX_OPS_ORDER_LIFECYCLE_GREEN "
        "handoff=review_only queue=idempotent quote=approval_gated network=false mutation=false"
    )


if __name__ == "__main__":
    main()

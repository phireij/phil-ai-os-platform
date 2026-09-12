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
    OrderQuoteApprovalDecisionProposalRegister,
    OrderQuoteApprovalRequestRegister,
    OrderQuoteOwnerDecisionPacketError,
    OrderQuotePreparationError,
    OrderReviewQueue,
    build_order_quote_approval_decision_proposal,
    build_order_quote_approval_request,
    build_order_quote_draft,
    build_order_quote_owner_decision_packet,
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


def expect_quote_preparation_blocked(review: dict[str, Any], decision: str) -> None:
    proposal = build_order_review_decision_proposal(
        review,
        decision,
        "staff:synthetic-branch-matrix",
        "Synthetic branch-matrix validation only.",
    )
    assert_no_authority_expansion(proposal, f"review_branch.{decision}")
    try:
        build_order_quote_preparation(review, proposal)
    except OrderQuotePreparationError:
        return
    fail(f"{decision} unexpectedly became eligible for quote preparation")


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

    # Negative staff-review branches must stop before quote preparation.
    expect_quote_preparation_blocked(review, "request_customer_revision")
    expect_quote_preparation_blocked(review, "decline_request")

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

    approval_register = OrderQuoteApprovalRequestRegister()
    registered_request = approval_register.register(approval_request)
    duplicate_request = approval_register.register(approval_request)
    if registered_request.get("accepted") is not True or duplicate_request.get("duplicate") is not True:
        fail("quote approval request idempotency boundary changed")

    decision_proposal = build_order_quote_approval_decision_proposal(
        approval_request,
        recommendation="recommend_quote_approval",
        reviewer_ref="staff:synthetic-integration",
        note="Recommendation only; synthetic integration validation.",
    )
    proposal_register = OrderQuoteApprovalDecisionProposalRegister()
    registered_proposal = proposal_register.register(decision_proposal)
    duplicate_proposal = proposal_register.register(decision_proposal)
    if registered_proposal.get("accepted") is not True or duplicate_proposal.get("duplicate") is not True:
        fail("quote approval recommendation idempotency boundary changed")

    owner_packet = build_order_quote_owner_decision_packet(
        approval_register,
        proposal_register,
        approval_request_id=approval_request["approval_request_id"],
    )

    lifecycle = [
        normalized,
        review,
        proposal,
        preparation,
        draft,
        approval_request,
        decision_proposal,
        owner_packet,
    ]
    for index, stage in enumerate(lifecycle):
        if stage.get("lifecycle_correlation_id") != correlation_id:
            fail(f"correlation continuity failed at lifecycle stage {index}")
        assert_no_authority_expansion(stage, f"lifecycle[{index}]")

    if approval_request.get("state") != "approval_requested":
        fail("quote approval request did not remain approval_requested")
    if approval_request.get("approval", {}).get("decision") is not None:
        fail("synthetic lifecycle unexpectedly made an approval decision")
    if decision_proposal.get("state") != "recommendation_only":
        fail("quote recommendation did not remain recommendation_only")
    if owner_packet.get("state") != "awaiting_owner_decision":
        fail("owner packet did not stop at awaiting_owner_decision")
    if owner_packet.get("recommendation") != "recommend_quote_approval":
        fail("owner packet lost the quote-approval recommendation")
    if owner_packet.get("owner_decision", {}).get("decision") is not None:
        fail("synthetic lifecycle unexpectedly made an owner decision")

    # A bounded staff recommendation to revise the quote may reach owner review,
    # but it must remain recommendation-only and non-authorizing.
    revision_proposal = build_order_quote_approval_decision_proposal(
        approval_request,
        recommendation="request_quote_revision",
        reviewer_ref="staff:synthetic-branch-matrix",
        note="Synthetic quote-revision recommendation only.",
    )
    assert_no_authority_expansion(revision_proposal, "quote_revision_proposal")
    revision_register = OrderQuoteApprovalDecisionProposalRegister()
    revision_registered = revision_register.register(revision_proposal)
    if revision_registered.get("accepted") is not True:
        fail("quote revision recommendation was not registered")
    revision_packet = build_order_quote_owner_decision_packet(
        approval_register,
        revision_register,
        approval_request_id=approval_request["approval_request_id"],
    )
    if revision_packet.get("recommendation") != "request_quote_revision":
        fail("owner packet lost the quote-revision recommendation")
    if revision_packet.get("state") != "awaiting_owner_decision":
        fail("quote-revision packet did not remain awaiting_owner_decision")
    if revision_packet.get("owner_decision", {}).get("decision") is not None:
        fail("quote-revision branch unexpectedly made an owner decision")
    if revision_packet.get("lifecycle_correlation_id") != correlation_id:
        fail("quote-revision branch correlation continuity failed")
    assert_no_authority_expansion(revision_packet, "quote_revision_packet")

    # Conflicting staff recommendations must fail closed before an owner packet
    # can be constructed from ambiguous evidence.
    conflict_register = OrderQuoteApprovalDecisionProposalRegister()
    if conflict_register.register(decision_proposal).get("accepted") is not True:
        fail("quote approval recommendation was not accepted for conflict test")
    if conflict_register.register(revision_proposal).get("accepted") is not True:
        fail("quote revision recommendation was not accepted for conflict test")
    try:
        build_order_quote_owner_decision_packet(
            approval_register,
            conflict_register,
            approval_request_id=approval_request["approval_request_id"],
        )
    except OrderQuoteOwnerDecisionPacketError:
        pass
    else:
        fail("conflicting quote recommendations unexpectedly produced an owner packet")

    print(
        "PHIL_AI_OS_SPRINT_7_ORDER_LIFECYCLE_BRANCH_MATRIX_GREEN "
        "customer_revision=blocked decline=blocked quote_revision=owner_review_only "
        "recommendation_conflict=blocked"
    )
    print(
        "PHIL_AI_OS_SPRINT_7_CX_OPS_ORDER_LIFECYCLE_GREEN "
        "handoff=review_only queue=idempotent quote=approval_gated owner=awaiting_decision "
        "network=false mutation=false"
    )


if __name__ == "__main__":
    main()

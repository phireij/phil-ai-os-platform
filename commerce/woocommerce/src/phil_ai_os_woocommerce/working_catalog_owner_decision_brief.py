from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .working_catalog_owner_action_packet import (
    CatalogOwnerAction,
    build_working_catalog_owner_action_packet,
)
from .working_catalog_owner_draft_assistance import (
    WorkingCatalogOwnerDraftAssistance,
    build_working_catalog_owner_draft_assistance,
)


@dataclass(frozen=True)
class WorkingCatalogOwnerDecisionBrief:
    owner_decisions: tuple[CatalogOwnerAction, ...]
    post_decision_records: tuple[CatalogOwnerAction, ...]
    operational_evidence: tuple[CatalogOwnerAction, ...]
    deferred_authority_gates: tuple[CatalogOwnerAction, ...]
    needs_review: tuple[CatalogOwnerAction, ...]
    japanese_draft_action_keys: tuple[str, ...]
    production_ready: bool
    network_call_performed: bool = False
    mutation_authorized: bool = False
    production_publish_authorized: bool = False


_OWNER_CATEGORIES = {
    "owner_approval",
    "owner_scope_confirmation",
    "owner_catalog_input",
    "category_mapping",
}

_OPERATIONAL_CATEGORIES = {
    "media_ingestion_evidence",
    "catalog_identity_integrity",
}


def _bucket(action: CatalogOwnerAction) -> str:
    if action.category == "authority_gate":
        return "deferred_authority"
    if action.category == "owner_approval" and action.requirement == "catalog approval reference is missing":
        return "post_decision_record"
    if action.category in _OWNER_CATEGORIES:
        return "owner_decision"
    if action.category in _OPERATIONAL_CATEGORIES:
        return "operational_evidence"
    if action.category == "fulfillment_decision_or_evidence":
        normalized = action.requirement.casefold()
        if any(token in normalized for token in ("physical-fit", "evidence", "validation", "verification")):
            return "operational_evidence"
        return "owner_decision"
    return "needs_review"


def _draft_action_keys(
    actions: tuple[CatalogOwnerAction, ...],
    assistance: WorkingCatalogOwnerDraftAssistance,
) -> tuple[str, ...]:
    drafts = {draft.product_key: draft for draft in assistance.drafts}
    keys: list[str] = []
    for action in actions:
        if not action.product_key:
            continue
        draft = drafts.get(action.product_key)
        if draft is None:
            continue
        if action.requirement == "Japanese product name" and draft.proposed_japanese_name:
            keys.append(action.action_key)
        elif action.requirement == "Japanese description" and draft.proposed_japanese_description:
            keys.append(action.action_key)
    return tuple(sorted(keys))


def build_working_catalog_owner_decision_brief(
    catalog_payload: dict[str, Any],
    proposal_payload: dict[str, Any],
) -> WorkingCatalogOwnerDecisionBrief:
    """Separate CEO decisions from evidence work and intentionally deferred authority gates.

    The brief is a read-only projection of the canonical owner action packet. Japanese copy
    draft availability is advisory only and comes from the separately validated proposal-only
    assistance packet. No action is resolved, no decision value is supplied, and no production
    authority is granted.
    """

    packet = build_working_catalog_owner_action_packet(catalog_payload)
    assistance = build_working_catalog_owner_draft_assistance(catalog_payload, proposal_payload)
    if packet.network_call_performed or assistance.network_call_performed:
        raise ValueError("owner decision brief cannot consume data produced by network calls")
    if packet.mutation_authorized or assistance.mutation_authorized:
        raise ValueError("owner decision brief cannot render mutation authority")
    if packet.production_publish_authorized or assistance.production_publish_authorized:
        raise ValueError("owner decision brief cannot render publication authority")
    if assistance.owner_approved or assistance.canonical_apply_authorized:
        raise ValueError("draft assistance must remain proposal-only")
    if any(action.decision_value is not None for action in packet.actions):
        raise ValueError("owner decision brief cannot render supplied decision values")

    grouped: dict[str, list[CatalogOwnerAction]] = {
        "owner_decision": [],
        "post_decision_record": [],
        "operational_evidence": [],
        "deferred_authority": [],
        "needs_review": [],
    }
    for action in packet.actions:
        grouped[_bucket(action)].append(action)

    accounted = sum(len(items) for items in grouped.values())
    if accounted != len(packet.actions):
        raise ValueError("owner decision brief failed to account for every canonical action")

    owner_decisions = tuple(grouped["owner_decision"])
    return WorkingCatalogOwnerDecisionBrief(
        owner_decisions=owner_decisions,
        post_decision_records=tuple(grouped["post_decision_record"]),
        operational_evidence=tuple(grouped["operational_evidence"]),
        deferred_authority_gates=tuple(grouped["deferred_authority"]),
        needs_review=tuple(grouped["needs_review"]),
        japanese_draft_action_keys=_draft_action_keys(owner_decisions, assistance),
        production_ready=packet.production_ready,
    )


def _append_actions(
    lines: list[str],
    actions: tuple[CatalogOwnerAction, ...],
    draft_keys: set[str],
) -> None:
    if not actions:
        lines.append("None.")
        return
    for action in actions:
        context = f" — `{action.product_key}`" if action.product_key else ""
        lines.append(f"- [ ] {action.requirement}{context}")
        if action.action_key in draft_keys:
            lines.append(
                "  - Japanese draft available in `ruby-working-catalog-japanese-copy-draft-assistance.md`; accept or edit it in the owner worksheet."
            )
        lines.append(f"  - Action key: `{action.action_key}`")


def render_working_catalog_owner_decision_brief(
    brief: WorkingCatalogOwnerDecisionBrief,
) -> str:
    draft_keys = set(brief.japanese_draft_action_keys)
    total = (
        len(brief.owner_decisions)
        + len(brief.post_decision_records)
        + len(brief.operational_evidence)
        + len(brief.deferred_authority_gates)
        + len(brief.needs_review)
    )
    lines = [
        "# Initial Launch Catalog V1 — CEO Decision Brief",
        "",
        (
            "This is a read-only prioritization of the canonical Sprint 3 owner action packet. "
            "It separates catalog decisions from evidence work and authority gates; it does not "
            "supply or approve any decision."
        ),
        "",
        f"- Production readiness: **{'READY' if brief.production_ready else 'BLOCKED'}**",
        f"- Canonical unresolved actions accounted for: **{total}**",
        f"- CEO-controlled decisions: **{len(brief.owner_decisions)}**",
        f"- Japanese copy decisions with draft assistance: **{len(brief.japanese_draft_action_keys)}**",
        f"- Post-decision/system records: **{len(brief.post_decision_records)}**",
        f"- Operational/evidence items: **{len(brief.operational_evidence)}**",
        f"- Deferred authority gates: **{len(brief.deferred_authority_gates)}**",
        f"- Needs classification/review: **{len(brief.needs_review)}**",
        "- Network calls performed: **No**",
        "- WooCommerce mutation authorized: **No**",
        "- Production publication authorized: **No**",
        "",
        "## CEO-controlled decisions",
        "",
        (
            "These are the catalog values, classifications, scope confirmations and approvals "
            "that remain owner-controlled. Final catalog approval should only be given after the "
            "underlying product facts and required evidence are satisfactory."
        ),
        "",
    ]
    _append_actions(lines, brief.owner_decisions, draft_keys)
    lines.extend(
        [
            "",
            "## Post-decision/system record",
            "",
            "This is recorded after the corresponding owner approval; it is not a separate catalog-content decision.",
            "",
        ]
    )
    _append_actions(lines, brief.post_decision_records, draft_keys)
    lines.extend(
        [
            "",
            "## Operational / evidence work",
            "",
            (
                "These items require verification or source evidence rather than a new catalog-value decision. "
                "They remain blocking until evidence is complete and may be escalated if owner participation is required."
            ),
            "",
        ]
    )
    _append_actions(lines, brief.operational_evidence, draft_keys)
    lines.extend(
        [
            "",
            "## Deferred authority gates — no approval requested now",
            "",
            (
                "These are intentionally closed production gates. They must not be interpreted as a request to enable "
                "WooCommerce mutation or publication during catalog preparation."
            ),
            "",
        ]
    )
    _append_actions(lines, brief.deferred_authority_gates, draft_keys)
    lines.extend(["", "## Needs classification / review", ""])
    _append_actions(lines, brief.needs_review, draft_keys)
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            (
                "Checking, reviewing or completing items in this brief does not itself approve Initial Launch Catalog V1, "
                "apply Japanese draft copy, publish products, mutate WooCommerce, or increase Phil AI OS autonomy."
            ),
            "",
        ]
    )
    return "\n".join(lines)

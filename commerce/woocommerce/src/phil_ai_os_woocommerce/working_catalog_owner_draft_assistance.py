from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CatalogCopyDraft:
    product_key: str
    source_english_name: str
    source_english_description: str
    proposed_japanese_name: str | None
    proposed_japanese_description: str | None


@dataclass(frozen=True)
class WorkingCatalogOwnerDraftAssistance:
    drafts: tuple[CatalogCopyDraft, ...]
    owner_approved: bool = False
    canonical_apply_authorized: bool = False
    network_call_performed: bool = False
    mutation_authorized: bool = False
    production_publish_authorized: bool = False


def _product_key(product: Mapping[str, Any]) -> str:
    return str(
        product.get("sku")
        or product.get("parent_reference")
        or product.get("english_name")
        or "unknown"
    )


def _nonempty_string(value: Any, field: str, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"draft assistance {key} requires non-empty {field}")
    return value.strip()


def build_working_catalog_owner_draft_assistance(
    catalog_payload: dict[str, Any],
    proposal_payload: dict[str, Any],
) -> WorkingCatalogOwnerDraftAssistance:
    """Validate proposal-only Japanese copy against the current source-backed catalog.

    Draft assistance is deliberately separate from canonical owner input. Exact English source
    text is carried in the proposal packet as a stale-content guard. A proposal may exist only
    for a canonical Japanese field that is still missing; it can never satisfy catalog
    readiness, owner approval, WooCommerce mutation, or production publication authority.
    """

    if proposal_payload.get("schema_version") != "1.0":
        raise ValueError("draft assistance schema_version must be 1.0")
    if proposal_payload.get("proposal_state") != "draft_assistance_only":
        raise ValueError("draft assistance proposal_state must remain draft_assistance_only")
    for field in (
        "owner_approved",
        "canonical_apply_authorized",
        "network_call_performed",
        "mutation_authorized",
        "production_publish_authorized",
    ):
        if proposal_payload.get(field) is not False:
            raise ValueError(f"draft assistance must keep {field}=false")

    raw_products = catalog_payload.get("working_products")
    if not isinstance(raw_products, list):
        raise ValueError("working_products must be an array")
    catalog_by_key: dict[str, Mapping[str, Any]] = {}
    expected_keys: set[str] = set()
    for index, product in enumerate(raw_products):
        if not isinstance(product, Mapping):
            raise ValueError(f"working_products[{index}] must be an object")
        key = _product_key(product)
        if key in catalog_by_key:
            raise ValueError(f"duplicate working catalog key: {key}")
        catalog_by_key[key] = product
        if not product.get("japanese_name") or not product.get("japanese_description"):
            expected_keys.add(key)

    raw_drafts = proposal_payload.get("products")
    if not isinstance(raw_drafts, list):
        raise ValueError("draft assistance products must be an array")
    drafts: list[CatalogCopyDraft] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_drafts):
        if not isinstance(raw, Mapping):
            raise ValueError(f"draft assistance products[{index}] must be an object")
        key = _nonempty_string(raw.get("product_key"), "product_key", f"products[{index}]")
        if key in seen:
            raise ValueError(f"duplicate draft assistance product_key: {key}")
        seen.add(key)
        product = catalog_by_key.get(key)
        if product is None:
            raise ValueError(f"draft assistance references unknown product: {key}")

        source_name = _nonempty_string(raw.get("source_english_name"), "source_english_name", key)
        source_description = _nonempty_string(
            raw.get("source_english_description"), "source_english_description", key
        )
        if source_name != product.get("english_name"):
            raise ValueError(f"draft assistance English name is stale for {key}")
        if source_description != product.get("english_description"):
            raise ValueError(f"draft assistance English description is stale for {key}")

        proposed_name = raw.get("proposed_japanese_name")
        proposed_description = raw.get("proposed_japanese_description")
        if product.get("japanese_name"):
            if proposed_name is not None:
                raise ValueError(f"draft assistance cannot overwrite canonical Japanese name for {key}")
        else:
            proposed_name = _nonempty_string(proposed_name, "proposed_japanese_name", key)
        if product.get("japanese_description"):
            if proposed_description is not None:
                raise ValueError(
                    f"draft assistance cannot overwrite canonical Japanese description for {key}"
                )
        else:
            proposed_description = _nonempty_string(
                proposed_description, "proposed_japanese_description", key
            )

        drafts.append(
            CatalogCopyDraft(
                product_key=key,
                source_english_name=source_name,
                source_english_description=source_description,
                proposed_japanese_name=proposed_name,
                proposed_japanese_description=proposed_description,
            )
        )

    if seen != expected_keys:
        missing = sorted(expected_keys - seen)
        extra = sorted(seen - expected_keys)
        raise ValueError(f"draft assistance coverage mismatch: missing={missing} extra={extra}")

    drafts.sort(key=lambda item: item.product_key)
    return WorkingCatalogOwnerDraftAssistance(drafts=tuple(drafts))


def render_working_catalog_owner_draft_assistance_markdown(
    assistance: WorkingCatalogOwnerDraftAssistance,
) -> str:
    lines = [
        "# Working Catalog Japanese Copy — Draft Assistance",
        "",
        "> **Proposal only.** These Japanese names/descriptions are drafting assistance, not source-backed catalog facts and not owner approval. Accept or edit them in the owner worksheet before they can enter canonical catalog intake.",
        "",
    ]
    for draft in assistance.drafts:
        lines.extend(
            [
                f"## {draft.product_key} — {draft.source_english_name}",
                "",
                f"- Suggested Japanese name: **{draft.proposed_japanese_name or 'Already canonical'}**",
                f"- Suggested Japanese description: {draft.proposed_japanese_description or 'Already canonical'}",
                "",
            ]
        )
    lines.extend(
        [
            "## Authority boundary",
            "",
            "- Owner approved: **No**",
            "- Canonical apply authorized: **No**",
            "- Network calls performed: **No**",
            "- WooCommerce mutation authorized: **No**",
            "- Production publication authorized: **No**",
            "",
            "Completing or reviewing this draft does not approve Initial Launch Catalog V1.",
            "",
        ]
    )
    return "\n".join(lines)

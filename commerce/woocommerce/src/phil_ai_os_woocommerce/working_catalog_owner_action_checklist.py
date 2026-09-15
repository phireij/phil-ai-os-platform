from __future__ import annotations

from collections import defaultdict
from typing import Any

from .working_catalog_owner_action_packet import (
    CatalogOwnerAction,
    WorkingCatalogOwnerActionPacket,
    build_working_catalog_owner_action_packet,
)
from .working_catalog_owner_worksheet import (
    WorkingCatalogOwnerWorksheet,
    build_working_catalog_owner_worksheet,
)


def _validate_non_authorizing(packet: WorkingCatalogOwnerActionPacket) -> None:
    if packet.network_call_performed:
        raise ValueError("owner action checklist cannot render a packet that performed a network call")
    if packet.mutation_authorized:
        raise ValueError("owner action checklist cannot render mutation authority")
    if packet.production_publish_authorized:
        raise ValueError("owner action checklist cannot render production publication authority")
    if any(action.decision_value is not None for action in packet.actions):
        raise ValueError("owner action checklist cannot render supplied decision values")


def _append_action(lines: list[str], action: CatalogOwnerAction) -> None:
    lines.extend(
        (
            f"- [ ] {action.requirement}",
            f"  - Category: `{action.category}`",
            f"  - Action key: `{action.action_key}`",
            f"  - Source blocker: {action.source_blocker}",
        )
    )


def _rows_by_sku(worksheet: WorkingCatalogOwnerWorksheet) -> dict[str, dict[str, str]]:
    return {row["sku"]: row for row in worksheet.rows if row.get("sku")}


def _variation_rows_by_parent(
    worksheet: WorkingCatalogOwnerWorksheet,
) -> dict[str, tuple[dict[str, str], ...]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in worksheet.rows:
        if row.get("record_type") == "variation" and row.get("parent_sku"):
            grouped[row["parent_sku"]].append(row)
    return {
        parent_sku: tuple(sorted(rows, key=lambda row: row["sku"]))
        for parent_sku, rows in grouped.items()
    }


def render_working_catalog_owner_action_checklist(payload: dict[str, Any]) -> str:
    """Render unresolved catalog actions as a deterministic, human-readable checklist.

    This view is derived only from the canonical owner action packet and owner worksheet. It
    supplies no decisions, changes no catalog facts, performs no network calls, and grants no
    WooCommerce mutation or production publication authority.
    """

    packet = build_working_catalog_owner_action_packet(payload)
    worksheet = build_working_catalog_owner_worksheet(payload)
    _validate_non_authorizing(packet)

    global_actions = [action for action in packet.actions if action.scope == "global"]
    product_actions: dict[str, list[CatalogOwnerAction]] = defaultdict(list)
    for action in packet.actions:
        if action.scope == "product":
            if not action.product_key:
                raise ValueError("product-scoped owner action requires product_key")
            product_actions[action.product_key].append(action)
        elif action.scope != "global":
            raise ValueError(f"unsupported owner action scope: {action.scope!r}")

    rows_by_sku = _rows_by_sku(worksheet)
    variations_by_parent = _variation_rows_by_parent(worksheet)
    readiness = "READY" if packet.production_ready else "BLOCKED"
    lines = [
        "# Working Catalog Owner Checklist",
        "",
        (
            "Generated from the current deterministic owner action packet and owner worksheet. "
            "Every checked item must be resolved through source-backed owner or operational "
            "evidence; this view does not supply decisions or change catalog facts."
        ),
        "",
        f"- Production readiness: **{readiness}**",
        f"- Remaining actions: **{len(packet.actions)}**",
        "- Network calls performed: **No**",
        "- WooCommerce mutation authorized: **No**",
        "- Production publication authorized: **No**",
        "",
        "## Global actions",
        "",
    ]

    if global_actions:
        for action in global_actions:
            _append_action(lines, action)
    else:
        lines.append("No unresolved global actions.")

    lines.extend(("", "## Product actions", ""))
    if not product_actions:
        lines.append("No unresolved product actions.")
    else:
        for product_key in sorted(product_actions):
            row = rows_by_sku.get(product_key)
            if row is None:
                raise ValueError(f"product action has no matching owner worksheet row: {product_key}")
            record_type = row["record_type"]
            lines.extend(
                (
                    f"### {product_key}",
                    "",
                    f"- Owner worksheet row: `{record_type}` / `{product_key}`",
                )
            )
            variation_rows = variations_by_parent.get(product_key, ())
            if record_type == "variable_parent":
                if not variation_rows:
                    raise ValueError(f"variable parent has no owner worksheet variation rows: {product_key}")
                variation_skus = ", ".join(f"`{item['sku']}`" for item in variation_rows)
                lines.extend(
                    (
                        f"- Related variation SKUs (source-backed): {variation_skus}",
                        (
                            "- Product-level owner fields belong on the `variable_parent` row; "
                            "variation rows remain the source-backed SKU/attribute structure."
                        ),
                    )
                )
            elif record_type != "simple_product":
                raise ValueError(
                    f"product action maps to unsupported owner worksheet row type: {record_type!r}"
                )

            lines.append("")
            for action in product_actions[product_key]:
                _append_action(lines, action)
            lines.append("")

    lines.extend(
        (
            "## Guardrail",
            "",
            (
                "Completing this checklist is evidence preparation only. It does not itself "
                "approve Initial Launch Catalog V1, publish products, mutate WooCommerce, or "
                "increase Phil AI OS autonomy."
            ),
            "",
        )
    )
    return "\n".join(lines)

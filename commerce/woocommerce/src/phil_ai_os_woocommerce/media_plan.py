from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .models import MediaRecord, ProductRecord


class MediaPlanError(ValueError):
    """Raised when a product media projection would be ambiguous or incomplete."""


@dataclass(frozen=True)
class MediaReconciliationPlan:
    desired: tuple[dict[str, object], ...]
    replacement_keys: tuple[str, ...]
    removed_keys: tuple[str, ...]
    metadata_update_keys: tuple[str, ...]
    reordered: bool

    @property
    def action(self) -> str:
        if self.replacement_keys or self.removed_keys:
            return "replace"
        if self.metadata_update_keys and self.reordered:
            return "metadata_and_reorder"
        if self.metadata_update_keys:
            return "metadata"
        if self.reordered:
            return "reorder"
        return "noop"


def build_product_media_plan(
    product: ProductRecord,
    media_records: Iterable[MediaRecord],
    *,
    locale: str = "en",
) -> tuple[dict[str, object], ...]:
    """Build an ordered WooCommerce media manifest without uploading anything."""
    by_key: dict[str, MediaRecord] = {}
    for media in media_records:
        if media.key in by_key:
            raise MediaPlanError(f"duplicate media key: {media.key}")
        by_key[media.key] = media

    selected: list[MediaRecord] = []
    for key in product.media_keys:
        media = by_key.get(key)
        if media is None:
            raise MediaPlanError(f"product {product.sku} references missing media: {key}")
        selected.append(media)

    if not selected:
        return ()

    primaries = [media for media in selected if media.role == "primary"]
    if len(primaries) != 1:
        raise MediaPlanError(
            f"product {product.sku} must have exactly one primary image when media is present"
        )

    positions = [media.position for media in selected]
    if len(set(positions)) != len(positions):
        raise MediaPlanError(f"product {product.sku} has duplicate media positions")

    ordered = sorted(
        selected,
        key=lambda media: (0 if media.role == "primary" else 1, media.position, media.key),
    )
    return tuple(media.upload_manifest(locale) for media in ordered)


def plan_media_reconciliation(
    desired: tuple[dict[str, object], ...],
    observed: Iterable[Mapping[str, object]],
) -> MediaReconciliationPlan:
    """Diff canonical media projections without performing uploads or mutations.

    `observed` is an already-normalized read model from an isolated/mock adapter.
    It intentionally does not imply that live WooCommerce media APIs are enabled.
    """
    observed_items = tuple(dict(item) for item in observed)
    desired_by_key = {str(item.get("key", "")): item for item in desired}
    observed_by_key = {str(item.get("key", "")): item for item in observed_items}

    if "" in desired_by_key or "" in observed_by_key:
        raise MediaPlanError("media reconciliation requires stable non-empty keys")
    if len(desired_by_key) != len(desired) or len(observed_by_key) != len(observed_items):
        raise MediaPlanError("media reconciliation keys must be unique")

    replacement_keys = sorted(
        key
        for key, item in desired_by_key.items()
        if key not in observed_by_key
        or item.get("source_ref") != observed_by_key[key].get("source_ref")
    )
    removed_keys = sorted(key for key in observed_by_key if key not in desired_by_key)

    metadata_fields = ("alt", "role", "position")
    metadata_update_keys = sorted(
        key
        for key, item in desired_by_key.items()
        if key in observed_by_key
        and item.get("source_ref") == observed_by_key[key].get("source_ref")
        and any(item.get(field) != observed_by_key[key].get(field) for field in metadata_fields)
    )

    desired_order = [str(item["key"]) for item in desired]
    observed_common_order = [
        str(item["key"])
        for item in observed_items
        if str(item.get("key", "")) in desired_by_key
    ]
    desired_common_order = [key for key in desired_order if key in observed_by_key]
    reordered = desired_common_order != observed_common_order

    return MediaReconciliationPlan(
        desired=desired,
        replacement_keys=tuple(replacement_keys),
        removed_keys=tuple(removed_keys),
        metadata_update_keys=tuple(metadata_update_keys),
        reordered=reordered,
    )

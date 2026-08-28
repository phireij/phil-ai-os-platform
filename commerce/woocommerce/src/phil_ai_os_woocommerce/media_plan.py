from __future__ import annotations

from typing import Iterable

from .models import MediaRecord, ProductRecord


class MediaPlanError(ValueError):
    """Raised when a product media projection would be ambiguous or incomplete."""


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

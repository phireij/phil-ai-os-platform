from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def idempotency_key(operation: str, entity_type: str, entity_key: str, payload: Mapping[str, Any]) -> str:
    material = {
        "operation": operation,
        "entity_type": entity_type,
        "entity_key": entity_key,
        "payload": payload,
    }
    return f"phil:{hashlib.sha256(canonical_json(material).encode('utf-8')).hexdigest()}"


@dataclass(frozen=True)
class ReconciliationResult:
    action: str
    entity_key: str
    idempotency_key: str
    remote_id: int | None
    before_fingerprint: str | None
    after_fingerprint: str


class MemoryIdempotencyStore:
    def __init__(self) -> None:
        self._results: dict[str, ReconciliationResult] = {}

    def get(self, key: str) -> ReconciliationResult | None:
        return self._results.get(key)

    def put(self, result: ReconciliationResult) -> None:
        self._results[result.idempotency_key] = result


def comparable_remote_product(remote: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "sku",
        "name",
        "description",
        "slug",
        "regular_price",
        "status",
        "catalog_visibility",
        "shipping_class",
    )
    comparable = {field: remote.get(field) for field in fields}
    target_meta = {
        "_philaios_temperature_modes",
        "_philaios_pickup_allowed",
        "_philaios_delivery_allowed",
        "_philaios_requires_order_approval",
    }
    comparable["meta_data"] = [
        {"key": item.get("key"), "value": item.get("value")}
        for item in remote.get("meta_data", [])
        if isinstance(item, Mapping) and item.get("key") in target_meta
    ]
    return comparable

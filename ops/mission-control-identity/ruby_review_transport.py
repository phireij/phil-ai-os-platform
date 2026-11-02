"""Disabled-by-default synthetic Ruby review-record read adapter.

The adapter has no environment switch, listener, credential, or default
binding.  A reviewed runtime would need a separate protected owner/project
policy and activation decision.  Tests inject a disposable binding whose
records are created through the existing encrypted Core producer.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

from conversation_store import ConversationConfig, ConversationRequestError, ConversationStore


RUBY_PROJECT = "rubys-cake-delights-hq"


@dataclass(frozen=True)
class SyntheticReceipt:
    reference: str
    kind: str
    record_id: str
    idempotency_key: str
    request_body: bytes
    revision_number: int
    catalog_revision: str
    fingerprint: str
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class SyntheticRecord:
    record_id: str
    project_id: str
    create_receipt: SyntheticReceipt
    revision_receipt: SyntheticReceipt | None


class RubySyntheticReadBinding:
    """A protected server-side owner/project binding for test-only fixtures."""

    def __init__(
        self,
        *,
        store: ConversationStore,
        issuer: str,
        owner_subject: str,
        project_id: str,
        records: tuple[SyntheticRecord, ...],
    ) -> None:
        self.store = store
        self.issuer = issuer
        self.owner_subject = owner_subject
        self.project_id = project_id
        self.records = records
        self._by_record = {record.record_id: record for record in records}
        self._by_receipt = {
            receipt.reference: receipt
            for record in records
            for receipt in (record.create_receipt, record.revision_receipt)
            if receipt is not None
        }

    def is_available_for(self, server_owner_subject: str) -> bool:
        return (
            bool(self.records)
            and self.project_id == RUBY_PROJECT
            and hmac.compare_digest(self.owner_subject, server_owner_subject)
            and self.store.matches_owner_context(self.issuer, self.owner_subject)
            and self.project_id in self.store._ruby_review_projects
        )

    def _require_exact_store_context(self) -> None:
        if not (
            bool(self.records)
            and self.project_id == RUBY_PROJECT
            and self.store.matches_owner_context(self.issuer, self.owner_subject)
            and self.project_id in self.store._ruby_review_projects
        ):
            raise ConversationRequestError("synthetic_binding_unavailable", 503)

    def _record(self, record_id: str) -> SyntheticRecord:
        self._require_exact_store_context()
        record = self._by_record.get(record_id)
        if record is None:
            raise ConversationRequestError("not_found", 404)
        return record

    @staticmethod
    def _safe_record(value: dict[str, Any]) -> dict[str, Any]:
        projection = value["projection"]
        return {
            "record_id": value["record_id"],
            "project_id": value["project_id"],
            "state": value["state"],
            "revision_id": value["revision_id"],
            "revision_number": value["revision_number"],
            "catalog_revision": projection["catalog_revision"],
            "source_packet_fingerprint": projection["source_packet_fingerprint"],
            "items": projection["items"],
            "fulfillment_preference": projection["fulfillment_preference"],
            "unresolved_blockers": projection["unresolved_blockers"],
            "customer_confirmation": False,
            "synthetic": True,
            "authority_effect": "none",
            "execution_authorized": False,
            "mutation_authorized": False,
        }

    def list_records(self) -> dict[str, Any]:
        self._require_exact_store_context()
        result = self.store.list_ruby_review_records(self.project_id, limit=50)
        records = [
            self._safe_record(value) for value in result["records"]
            if value["record_id"] in self._by_record
        ]
        if len(records) != len(self.records):
            raise ConversationRequestError("synthetic_binding_unavailable", 503)
        return {"records": records, "authority_effect": "none", "exports_enabled": False}

    def get_record(self, record_id: str) -> dict[str, Any]:
        self._record(record_id)
        return self._safe_record(self.store.get_ruby_review_record(record_id))

    def list_audit(self, record_id: str) -> dict[str, Any]:
        self._record(record_id)
        result = self.store.list_ruby_review_audit(record_id, limit=50)
        return {
            "record_id": record_id,
            "events": result["events"],
            "authority_effect": "none",
            "synthetic": True,
        }

    def resolve_receipt(self, reference: str) -> dict[str, Any]:
        self._require_exact_store_context()
        receipt = self._by_receipt.get(reference)
        if receipt is None:
            raise ConversationRequestError("not_found", 404)
        if receipt.kind == "create":
            result = self.store.resolve_ruby_review_create_receipt(
                receipt.idempotency_key, receipt.request_body
            )
        else:
            result = self.store.resolve_ruby_review_revision_receipt(
                receipt.record_id, receipt.idempotency_key, receipt.request_body
            )
        return {
            "receipt_reference": receipt.reference,
            "state": result["state"],
            "reason": result.get("reason"),
            "receipt": result.get("receipt"),
            "authority_effect": "none",
            "retry_authorized": False,
            "synthetic": True,
        }


def _payload(*, label: str, catalog_revision: str, fingerprint: str, fulfillment: str, blockers: list[str]) -> bytes:
    return json.dumps({
        "schema_version": "ruby.pending-review.v1",
        "project_id": RUBY_PROJECT,
        "catalog_revision": catalog_revision,
        "source_packet_fingerprint": "sha256:" + fingerprint,
        "source_review_ref": "controlled-fixture:" + label,
        "correlation_ref": "controlled-fixture-correlation:" + label,
        "items": [{"sku": "RCD-" + label.upper(), "quantity": 1, "item_subtotal_minor": 1200}],
        "fulfillment_preference": fulfillment,
        "unresolved_blockers": blockers,
        "customer_confirmation": False,
    }, separators=(",", ":")).encode("utf-8")


def build_disposable_synthetic_binding(
    config: ConversationConfig, *, owner_subject: str, issuer: str
) -> RubySyntheticReadBinding:
    """Seed controlled pickup, Yamato, and Ruby-car fixtures in a disposable Core."""
    store = ConversationStore(config, issuer, owner_subject, ruby_review_projects=frozenset({RUBY_PROJECT}))
    records: list[SyntheticRecord] = []
    for label, fulfillment, blocker in (
        ("pickup", "store pickup", "controlled pickup timing fixture"),
        ("yamato", "Yamato delivery", "controlled Yamato service fixture"),
        ("ruby-car", "Ruby car delivery", "controlled Ruby car coverage fixture"),
    ):
        first = _payload(
            label=label,
            catalog_revision="catalog_" + label.replace("-", "_") + "_fixture_v1",
            fingerprint=hashlib.sha256((label + ":v1").encode()).hexdigest(),
            fulfillment=fulfillment,
            blockers=[blocker],
        )
        create_key = "ruby-transport-create-" + label + "-0001"
        created = store.create_ruby_review_record(create_key, first)
        create_receipt = SyntheticReceipt(
            "create-" + label, "create", created["record_id"], create_key, first, 1,
            json.loads(first)["catalog_revision"], json.loads(first)["source_packet_fingerprint"], tuple([blocker]),
        )
        revision_receipt = None
        if label == "pickup":
            second = _payload(
                label=label,
                catalog_revision="catalog_pickup_fixture_v2",
                fingerprint=hashlib.sha256(b"pickup:v2").hexdigest(),
                fulfillment=fulfillment,
                blockers=["controlled pickup revision fixture"],
            )
            revision_body = json.dumps({
                "expected_revision_id": created["revision_id"], "projection": json.loads(second),
            }, separators=(",", ":")).encode("utf-8")
            revision_key = "ruby-transport-revise-pickup-0001"
            revised = store.revise_ruby_review_record(created["record_id"], revision_key, revision_body)
            revision_receipt = SyntheticReceipt(
                "revise-pickup", "revise", created["record_id"], revision_key, revision_body, 2,
                json.loads(second)["catalog_revision"], json.loads(second)["source_packet_fingerprint"],
                ("controlled pickup revision fixture",),
            )
            third = _payload(
                label=label,
                catalog_revision="catalog_pickup_fixture_v3",
                fingerprint=hashlib.sha256(b"pickup:v3").hexdigest(),
                fulfillment=fulfillment,
                blockers=["controlled later catalog fixture"],
            )
            later_body = json.dumps({
                "expected_revision_id": revised["revision_id"], "projection": json.loads(third),
            }, separators=(",", ":")).encode("utf-8")
            store.revise_ruby_review_record(created["record_id"], "ruby-transport-revise-pickup-0002", later_body)
        records.append(SyntheticRecord(created["record_id"], RUBY_PROJECT, create_receipt, revision_receipt))
    return RubySyntheticReadBinding(
        store=store, issuer=issuer, owner_subject=owner_subject, project_id=RUBY_PROJECT, records=tuple(records)
    )

"""Fail-closed verification for immutable project evidence references."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import Any


PROJECTS = {"phil-ai-os", "rubys-cake-delights-hq", "kcfc-portal"}
REFERENCE = re.compile(r"evidence:sha256:[0-9a-f]{64}")


class EvidenceVerificationError(ValueError):
    pass


class EvidenceReferenceVerifier:
    """Verifies a signed, project-scoped immutable-reference manifest."""

    def __init__(self, records: dict[str, frozenset[str]]) -> None:
        self._records = records

    @classmethod
    def from_file(cls, path: Path, signing_key: bytes) -> "EvidenceReferenceVerifier":
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EvidenceVerificationError("evidence_manifest_unavailable") from exc
        return cls.from_document(document, signing_key)

    @classmethod
    def from_document(cls, document: Any, signing_key: bytes) -> "EvidenceReferenceVerifier":
        if not isinstance(document, dict) or set(document) != {"schema", "version", "references", "signature"}:
            raise EvidenceVerificationError("evidence_manifest_invalid")
        if document["schema"] != "phil-ai-os-mission-control-evidence-manifest" or document["version"] != 1:
            raise EvidenceVerificationError("evidence_manifest_invalid")
        signature = document["signature"]
        if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature):
            raise EvidenceVerificationError("evidence_manifest_invalid")
        body = {key: document[key] for key in ("schema", "version", "references")}
        expected = hmac.new(signing_key, json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected) or not isinstance(document["references"], list):
            raise EvidenceVerificationError("evidence_manifest_invalid")
        records: dict[str, set[str]] = {project: set() for project in PROJECTS}
        for item in document["references"]:
            if not isinstance(item, dict) or set(item) != {"project_id", "ref", "source_kind", "observed_at"}:
                raise EvidenceVerificationError("evidence_manifest_invalid")
            if item["project_id"] not in PROJECTS or not isinstance(item["ref"], str) or not REFERENCE.fullmatch(item["ref"]):
                raise EvidenceVerificationError("evidence_manifest_invalid")
            if not isinstance(item["source_kind"], str) or not item["source_kind"] or not isinstance(item["observed_at"], str) or not item["observed_at"]:
                raise EvidenceVerificationError("evidence_manifest_invalid")
            records[item["project_id"]].add(item["ref"])
        return cls({project: frozenset(refs) for project, refs in records.items()})

    def verify(self, project_id: str, references: list[str]) -> None:
        if project_id not in PROJECTS or any(not REFERENCE.fullmatch(reference) for reference in references):
            raise EvidenceVerificationError("evidence_reference_invalid")
        if not set(references).issubset(self._records[project_id]):
            raise EvidenceVerificationError("evidence_reference_not_authorized")

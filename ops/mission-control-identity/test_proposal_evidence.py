from __future__ import annotations

import hashlib
import hmac
import json
import unittest

from proposal_evidence import EvidenceReferenceVerifier, EvidenceVerificationError
from conversation_store import ConversationRequestError, ConversationStore


KEY = b"e" * 32
REF = "evidence:sha256:" + "a" * 64


def signed_document(references: list[dict[str, str]]) -> dict[str, object]:
    body: dict[str, object] = {
        "schema": "phil-ai-os-mission-control-evidence-manifest",
        "version": 1,
        "references": references,
    }
    body["signature"] = hmac.new(KEY, json.dumps(body, sort_keys=True, separators=(",", ":")).encode(), hashlib.sha256).hexdigest()
    return body


class ProposalEvidenceChecks(unittest.TestCase):
    def manifest(self, document: dict[str, object]) -> EvidenceReferenceVerifier:
        return EvidenceReferenceVerifier.from_document(document, KEY)

    def test_signed_project_scoped_reference_is_accepted(self) -> None:
        verifier = self.manifest(signed_document([{
            "project_id": "phil-ai-os", "ref": REF, "source_kind": "project_state", "observed_at": "2026-10-15T00:00:00Z",
        }]))
        verifier.verify("phil-ai-os", [REF])
        with self.assertRaisesRegex(EvidenceVerificationError, "evidence_reference_not_authorized"):
            verifier.verify("kcfc-portal", [REF])

    def test_tampered_manifest_is_rejected(self) -> None:
        document = signed_document([])
        document["references"] = [{"project_id": "phil-ai-os", "ref": REF, "source_kind": "project_state", "observed_at": "2026-10-15T00:00:00Z"}]
        with self.assertRaisesRegex(EvidenceVerificationError, "evidence_manifest_invalid"):
            self.manifest(document)

    def test_store_payload_fails_closed_without_manifest_and_keeps_verified_refs(self) -> None:
        payload = json.dumps({
            "source_message_id": "m" * 16, "project_id": "phil-ai-os", "task_class": "general",
            "scope": "Review a source.", "expected_result": "A note.", "required_authority": "A1",
            "source_evidence_refs": [REF],
        }).encode()
        store = object.__new__(ConversationStore)
        store._evidence_verifier = None
        with self.assertRaisesRegex(ConversationRequestError, "evidence_reference_verification_unavailable"):
            store._proposal_payload(payload)
        store._evidence_verifier = self.manifest(signed_document([{
            "project_id": "phil-ai-os", "ref": REF, "source_kind": "project_state", "observed_at": "2026-10-15T00:00:00Z",
        }]))
        self.assertEqual([REF], store._proposal_payload(payload)["source_evidence_refs"])


if __name__ == "__main__":
    unittest.main()

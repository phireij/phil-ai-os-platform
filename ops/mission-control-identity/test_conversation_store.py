"""Focused offline checks for the inactive CEO conversation foundation."""

from __future__ import annotations

import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from conversation_recovery import BACKUP_MAX_AGE_SECONDS, create_backup, restore_to_quarantine
from conversation_store import (
    RETENTION_SECONDS,
    ConversationConfig,
    ConversationConfigurationError,
    ConversationRequestError,
    ConversationStore,
)


ISSUER = "https://accounts.google.com"
SUBJECT = "synthetic-owner-subject"


class ConversationStoreChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temp.name)
        if os.name != "nt":
            os.chmod(self.root, 0o700)
        self.key = self.root / "key"
        self.key.write_text("22" * 32, encoding="ascii")
        if os.name != "nt":
            os.chmod(self.key, 0o600)
        self.config = ConversationConfig(self.root / "state.enc", self.root / "ledger.enc", self.key)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def store(self, subject: str = SUBJECT) -> ConversationStore:
        return ConversationStore(self.config, ISSUER, subject)

    def test_disabled_by_default_and_protected_configuration_fail_closed(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(ConversationConfig.from_environment())
        with patch.dict(os.environ, {"MISSION_CONTROL_CONVERSATION_ENABLED": "true"}, clear=True):
            with self.assertRaises(ConversationConfigurationError):
                ConversationConfig.from_environment()

    def test_encrypted_persistence_idempotency_and_owner_isolation(self) -> None:
        store = self.store()
        created = store.create_conversation("create-conversation-0001", b"{}")
        replay = store.create_conversation("create-conversation-0001", b"{}")
        self.assertEqual(created, replay)
        conversation_id = created["conversation_id"]
        message = store.submit_message(
            conversation_id,
            "submit-conversation-0001",
            b'{"body":"synthetic plaintext marker"}',
        )
        self.assertEqual(message["response_state"], "unavailable")
        self.assertEqual(message["error_code"], "runtime_unavailable")
        self.assertNotIn(b"synthetic plaintext marker", self.config.state_file.read_bytes())
        self.assertNotIn(conversation_id.encode(), self.config.state_file.read_bytes())
        self.assertEqual(len(store.list_messages(conversation_id)), 1)

        other = self.store("different-owner-subject")
        self.assertEqual(other.list_conversations(), [])
        with self.assertRaisesRegex(ConversationRequestError, "not_found"):
            other.list_messages(conversation_id)

    def test_conflicting_idempotency_and_failed_persistence_roll_back(self) -> None:
        store = self.store()
        created = store.create_conversation("create-conversation-0002", b"{}")
        conversation_id = created["conversation_id"]
        store.submit_message(
            conversation_id, "submit-conversation-0002", b'{"body":"first"}'
        )
        with self.assertRaisesRegex(ConversationRequestError, "idempotency_conflict"):
            store.submit_message(
                conversation_id, "submit-conversation-0002", b'{"body":"second"}'
            )
        before = store.list_conversations()
        with patch.object(store._live, "persist", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                store.create_conversation("create-conversation-0003", b"{}")
        self.assertEqual(store.list_conversations(), before)

    def test_governed_proposal_and_decision_are_owner_bound_and_non_authorizing(self) -> None:
        store = self.store()
        conversation = store.create_conversation("create-conversation-0091", b"{}")
        message = store.submit_message(conversation["conversation_id"], "submit-conversation-0091", b'{"body":"prepare a bounded draft"}')
        proposal_body = ("{" + f'"source_message_id":"{message["message_id"]}","project_id":"phil-ai-os","task_class":"general","scope":"Review one bounded artifact.","expected_result":"A review note.","required_authority":"A1","source_evidence_refs":[]' + "}").encode()
        proposal = store.create_task_proposal(conversation["conversation_id"], "proposal-conversation-0001", proposal_body)
        self.assertEqual("draft", proposal["proposal_state"])
        self.assertFalse(proposal["execution_authorized"])
        self.assertIsNone(proposal["assignment_id"])
        self.assertEqual(proposal, store.create_task_proposal(conversation["conversation_id"], "proposal-conversation-0001", proposal_body))
        decision = store.record_task_decision(proposal["proposal_id"], "decision-proposal-0001", b'{"decision":"approved","rationale":"Proceed only through a later gate.","expires_at":"2030-01-01T00:00:00Z"}')
        self.assertEqual({"project_id": "phil-ai-os", "required_authority": "A1"}, decision["decision_scope"])
        self.assertFalse(decision["mutation_authorized"])
        with self.assertRaisesRegex(ConversationRequestError, "decision_already_recorded"):
            store.record_task_decision(proposal["proposal_id"], "decision-proposal-0002", b'{"decision":"rejected","rationale":"No.","expires_at":"2030-01-01T00:00:00Z"}')

        timeline = store.list_audit_timeline(conversation["conversation_id"])
        self.assertEqual(
            ["conversation_created", "ceo_message_submitted", "task_proposal_drafted", "ceo_decision_recorded"],
            [event["event_type"] for event in timeline["events"]],
        )
        self.assertEqual("none", timeline["authority_effect"])
        self.assertNotIn("prepare a bounded draft", json.dumps(timeline))
        self.assertNotIn("Proceed only through a later gate.", json.dumps(timeline))
        coverage = {entry["source"]: entry["status"] for entry in timeline["source_coverage"]}
        self.assertEqual("available", coverage["notification_outbox"])
        self.assertEqual("not_available", coverage["task_execution"])
        first_page = store.list_audit_timeline(conversation["conversation_id"], limit=1)
        self.assertEqual("1", first_page["next_cursor"])
        self.assertEqual("ceo_message_submitted", store.list_audit_timeline(conversation["conversation_id"], limit=1, cursor=1)["events"][0]["event_type"])
        notifications = store.list_notifications()
        self.assertEqual("not_configured", notifications["transport_status"])
        self.assertEqual(1, len(notifications["notifications"]))
        notification = notifications["notifications"][0]
        self.assertEqual("ceo_decision_recorded", notification["kind"])
        self.assertEqual("not_configured", notification["delivery_state"])
        self.assertEqual(0, notification["attempt_count"])
        self.assertNotIn("Proceed only through a later gate.", json.dumps(notifications))

    def test_retention_and_durable_deletion_marker_prevent_reappearance(self) -> None:
        now = 2_000_000_000
        with patch("conversation_store.time.time", return_value=now):
            store = self.store()
            conversation_id = store.create_conversation(
                "create-conversation-0004", b"{}"
            )["conversation_id"]
            store.delete_conversation(conversation_id)
        reopened = self.store()
        self.assertEqual(reopened.list_conversations(), [])

        with patch("conversation_store.time.time", return_value=now):
            retained = self.store()
            retained.create_conversation("create-conversation-0005", b"{}")
        with patch("conversation_store.time.time", return_value=now + RETENTION_SECONDS + 1):
            self.assertEqual(retained.list_conversations(), [])

    def test_backup_restore_replays_current_deletion_and_rejects_expiry_tamper_and_wrong_key(self) -> None:
        now = 2_000_000_000
        with patch("conversation_store.time.time", return_value=now):
            store = self.store()
            conversation_id = store.create_conversation(
                "create-conversation-0006", b"{}"
            )["conversation_id"]
        backup = self.root / "backup.enc"
        create_backup(self.config, backup, now)
        with patch("conversation_store.time.time", return_value=now + 1):
            store.delete_conversation(conversation_id)

        restored_state = self.root / "restored-state.enc"
        restored_ledger = self.root / "restored-ledger.enc"
        restore_to_quarantine(
            self.config,
            backup,
            restored_state,
            restored_ledger,
            now + BACKUP_MAX_AGE_SECONDS - 1,
        )
        restored = ConversationStore(
            ConversationConfig(restored_state, restored_ledger, self.key), ISSUER, SUBJECT
        )
        self.assertEqual(restored.list_conversations(), [])

        with self.assertRaisesRegex(ConversationConfigurationError, "backup_expired"):
            restore_to_quarantine(
                self.config,
                backup,
                self.root / "expired-state.enc",
                self.root / "expired-ledger.enc",
                now + BACKUP_MAX_AGE_SECONDS,
            )
        tampered = self.root / "tampered.enc"
        encoded = bytearray(backup.read_bytes())
        encoded[-1] ^= 1
        tampered.write_bytes(encoded)
        if os.name != "nt":
            os.chmod(tampered, 0o600)
        with self.assertRaisesRegex(ConversationConfigurationError, "backup_unavailable"):
            restore_to_quarantine(
                self.config,
                tampered,
                self.root / "tampered-state.enc",
                self.root / "tampered-ledger.enc",
                now + 1,
            )

        wrong_key = self.root / "wrong-key"
        wrong_key.write_text("33" * 32, encoding="ascii")
        if os.name != "nt":
            os.chmod(wrong_key, 0o600)
        wrong_config = ConversationConfig(
            self.config.state_file, self.config.deletion_ledger_file, wrong_key
        )
        with self.assertRaisesRegex(ConversationConfigurationError, "backup_unavailable"):
            restore_to_quarantine(
                wrong_config,
                backup,
                self.root / "wrong-state.enc",
                self.root / "wrong-ledger.enc",
                now + 1,
            )


if __name__ == "__main__":
    unittest.main()

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

    @staticmethod
    def _record_decision(store: ConversationStore, suffix: str) -> dict:
        conversation = store.create_conversation(f"create-notification-{suffix}", b"{}")
        message = store.submit_message(
            conversation["conversation_id"], f"submit-notification-{suffix}", b'{"body":"bounded notification test"}'
        )
        proposal = store.create_task_proposal(
            conversation["conversation_id"],
            f"proposal-notification-{suffix}",
            (
                "{" + f'"source_message_id":"{message["message_id"]}",'
                '"project_id":"phil-ai-os","task_class":"general",'
                '"scope":"Review one bounded artifact.","expected_result":"A review note.",'
                '"required_authority":"A1","source_evidence_refs":[]}'
            ).encode(),
        )
        return store.record_task_decision(
            proposal["proposal_id"],
            f"decision-notification-{suffix}",
            b'{"decision":"approved","rationale":"Bounded notification-only test.","expires_at":"2035-01-01T00:00:00Z"}',
        )

    def test_disabled_by_default_and_protected_configuration_fail_closed(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(ConversationConfig.from_environment())
        with patch.dict(os.environ, {"MISSION_CONTROL_CONVERSATION_ENABLED": "true"}, clear=True):
            with self.assertRaises(ConversationConfigurationError):
                ConversationConfig.from_environment()

    @unittest.skipIf(os.name == "nt", "POSIX permissions are required")
    def test_exact_sticky_volume_parent_is_the_only_non_private_exception(self) -> None:
        sticky = self.root / "sticky-volume-state"
        sticky.mkdir(mode=0o1777)
        os.chmod(sticky, 0o1777)
        environment = {
            "MISSION_CONTROL_CONVERSATION_ENABLED": "true",
            "MISSION_CONTROL_CONVERSATION_STATE_FILE": str(sticky / "state.enc"),
            "MISSION_CONTROL_CONVERSATION_DELETION_LEDGER_FILE": str(sticky / "ledger.enc"),
            "MISSION_CONTROL_CONVERSATION_KEY_FILE": str(self.key),
        }
        with patch.dict(os.environ, environment, clear=True):
            self.assertIsNotNone(ConversationConfig.from_environment())

        insecure = self.root / "insecure-state"
        insecure.mkdir(mode=0o777)
        os.chmod(insecure, 0o777)
        environment["MISSION_CONTROL_CONVERSATION_STATE_FILE"] = str(insecure / "state.enc")
        environment["MISSION_CONTROL_CONVERSATION_DELETION_LEDGER_FILE"] = str(insecure / "ledger.enc")
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ConversationConfigurationError, "parent_permissions"):
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

    def test_readonly_preflight_decrypts_without_rewriting_encrypted_state(self) -> None:
        self.store()
        before = (self.config.state_file.read_bytes(), self.config.deletion_ledger_file.read_bytes())
        with patch.dict(
            os.environ,
            {"MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT": "true"},
            clear=False,
        ):
            candidate = self.store()
        self.assertEqual([], candidate.list_conversations())
        self.assertEqual(before, (self.config.state_file.read_bytes(), self.config.deletion_ledger_file.read_bytes()))

    def test_readonly_preflight_rejects_unrecognized_value(self) -> None:
        with patch.dict(
            os.environ,
            {"MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT": "false"},
            clear=False,
        ):
            with self.assertRaisesRegex(ConversationConfigurationError, "readonly_preflight_invalid"):
                self.store()

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

        handoff = store.create_cto_handoff(proposal["proposal_id"], "handoff-proposal-0001", b"{}")
        self.assertEqual("awaiting_connector", handoff["state"])
        self.assertFalse(handoff["dispatch_authorized"])
        self.assertEqual(handoff, store.create_cto_handoff(proposal["proposal_id"], "handoff-proposal-0001", b"{}"))
        self.assertEqual([handoff], store.list_cto_handoffs(conversation["conversation_id"]))
        timeline = store.list_audit_timeline(conversation["conversation_id"])
        self.assertIn("cto_handoff_requested", [event["event_type"] for event in timeline["events"]])
        coverage = {entry["source"]: entry["status"] for entry in timeline["source_coverage"]}
        self.assertEqual("available", coverage["conversation_store.cto_handoffs"])
        self.assertEqual("awaiting_connector", coverage["task_assignment"])
        with self.assertRaisesRegex(ConversationRequestError, "handoff_already_recorded"):
            store.create_cto_handoff(proposal["proposal_id"], "handoff-proposal-0002", b"{}")

        with self.assertRaisesRegex(ConversationRequestError, "cto_identity_not_authorized"):
            store.get_cto_handoff_packet(
                handoff["handoff_id"],
                verified_cto_subject="auth0|wrong-cto",
                expected_cto_subject="auth0|approved-cto",
            )
        packet = store.get_cto_handoff_packet(
            handoff["handoff_id"],
            verified_cto_subject="auth0|approved-cto",
            expected_cto_subject="auth0|approved-cto",
        )
        self.assertEqual("Review one bounded artifact.", packet["scope"])
        self.assertFalse(packet["dispatch_authorized"])
        self.assertNotIn("Proceed only through a later gate.", json.dumps(packet))
        result_body = b'{"outcome":"completed","summary":"Reviewed the bounded artifact.","evidence_refs":["review:artifact-1"]}'
        result = store.record_cto_handoff_result(
            handoff["handoff_id"], "cto-result-handoff-0001", result_body,
            verified_cto_subject="auth0|approved-cto",
            expected_cto_subject="auth0|approved-cto",
        )
        self.assertEqual("completed", result["outcome"])
        self.assertFalse(result["execution_authorized"])
        results = store.list_cto_handoff_results(conversation["conversation_id"])
        self.assertEqual(1, len(results))
        self.assertEqual("Reviewed the bounded artifact.", results[0]["summary"])
        self.assertEqual(["review:artifact-1"], results[0]["evidence_refs"])
        self.assertFalse(results[0]["mutation_authorized"])
        self.assertEqual(
            result,
            store.record_cto_handoff_result(
                handoff["handoff_id"], "cto-result-handoff-0001", result_body,
                verified_cto_subject="auth0|approved-cto",
                expected_cto_subject="auth0|approved-cto",
            ),
        )
        self.assertEqual("result_recorded", store.list_cto_handoffs(conversation["conversation_id"])[0]["state"])
        with self.assertRaisesRegex(ConversationRequestError, "handoff_closed"):
            store.get_cto_handoff_packet(
                handoff["handoff_id"],
                verified_cto_subject="auth0|approved-cto",
                expected_cto_subject="auth0|approved-cto",
            )
        timeline = store.list_audit_timeline(conversation["conversation_id"])
        self.assertIn("cto_handoff_result_recorded", [event["event_type"] for event in timeline["events"]])
        self.assertNotIn("Reviewed the bounded artifact.", json.dumps(timeline))

    def test_enabled_delivery_is_identifier_only_retries_once_then_dead_letters(self) -> None:
        now = 1_900_000_000
        with patch("conversation_store.time.time", return_value=now):
            store = ConversationStore(
                self.config, ISSUER, SUBJECT, notification_delivery_enabled=True
            )
            decision = self._record_decision(store, "0001")
        notifications = store.list_notifications()
        self.assertEqual("enabled", notifications["transport_status"])
        self.assertEqual("pending", notifications["notifications"][0]["delivery_state"])

        delivered: list[dict] = []
        self.assertTrue(store.dispatch_one_notification(delivered.append, now=now, retry_seconds=900))
        self.assertEqual(1, len(delivered))
        self.assertEqual(decision["decision_id"], delivered[0]["decision_id"])
        self.assertNotIn("Bounded notification-only test.", json.dumps(delivered))
        self.assertEqual("delivered", store.list_notifications()["notifications"][0]["delivery_state"])

        with patch("conversation_store.time.time", return_value=now + 1):
            self._record_decision(store, "0002")

        def fail(_notification: dict) -> None:
            raise RuntimeError("telegram_request_rejected")

        self.assertTrue(store.dispatch_one_notification(fail, now=now + 1, retry_seconds=900))
        failed = store.list_notifications()["notifications"][1]
        self.assertEqual("retry_wait", failed["delivery_state"])
        self.assertEqual(1, failed["attempt_count"])
        self.assertEqual("telegram_request_rejected", failed["last_error"])
        self.assertFalse(store.dispatch_one_notification(fail, now=now + 900, retry_seconds=900))
        self.assertTrue(store.dispatch_one_notification(fail, now=now + 901, retry_seconds=900))
        failed = store.list_notifications()["notifications"][1]
        self.assertEqual("dead_letter", failed["delivery_state"])
        self.assertEqual(2, failed["attempt_count"])
        self.assertEqual("telegram_request_rejected", failed["last_error"])
        delivered_conversation_id = store._live.connection.execute(
            "SELECT p.conversation_id FROM ceo_decisions d "
            "JOIN task_proposals p ON p.proposal_id=d.proposal_id WHERE d.decision_id=?",
            (decision["decision_id"],),
        ).fetchone()["conversation_id"]
        failed_conversation_id = store._live.connection.execute(
            "SELECT p.conversation_id FROM ceo_decisions d "
            "JOIN task_proposals p ON p.proposal_id=d.proposal_id WHERE d.decision_id=?",
            (failed["decision_id"],),
        ).fetchone()["conversation_id"]
        delivery_events = [
            event for timeline in (
                store.list_audit_timeline(delivered_conversation_id),
                store.list_audit_timeline(failed_conversation_id),
            )
            for event in timeline["events"]
            if event["source"] == "notification_outbox"
        ]
        self.assertEqual(
            [
                "notification_delivery_delivered",
                "notification_delivery_retry_scheduled",
                "notification_delivery_dead_lettered",
            ],
            [event["event_type"] for event in delivery_events],
        )
        self.assertEqual(
            [None, "telegram_request_rejected", "telegram_request_rejected"],
            [event["correlation"]["error_code"] for event in delivery_events],
        )
        self.assertTrue(all(event["authority_effect"] == "none" for event in delivery_events))
        self.assertNotIn("Bounded notification-only test.", json.dumps(delivery_events))

        with patch("conversation_store.time.time", return_value=now + 902):
            self._record_decision(store, "0004")

        def unsafe_failure(_notification: dict) -> None:
            raise RuntimeError("untrusted failure text")

        self.assertTrue(store.dispatch_one_notification(unsafe_failure, now=now + 902, retry_seconds=900))
        self.assertEqual("delivery_failed", store.list_notifications()["notifications"][-1]["last_error"])

    def test_existing_outbox_snapshot_migrates_without_retroactive_delivery(self) -> None:
        original = self.store()
        with patch("conversation_store.time.time", return_value=1_900_000_000):
            self._record_decision(original, "0003")
        original._live.connection.execute("DROP TABLE notification_audit_events")
        original._live.connection.execute("DROP INDEX notification_outbox_delivery_order")
        original._live.connection.execute("DROP INDEX notification_outbox_owner_order")
        original._live.connection.execute("ALTER TABLE notification_outbox RENAME TO notification_outbox_new")
        original._live.connection.executescript(
            """
            CREATE TABLE notification_outbox (
                notification_id TEXT PRIMARY KEY,
                owner_digest BLOB NOT NULL,
                decision_id TEXT NOT NULL UNIQUE REFERENCES ceo_decisions(decision_id) ON DELETE CASCADE,
                proposal_id TEXT NOT NULL REFERENCES task_proposals(proposal_id) ON DELETE CASCADE,
                kind TEXT NOT NULL CHECK(kind='ceo_decision_recorded'),
                priority TEXT NOT NULL CHECK(priority IN ('low','medium','high','critical')),
                delivery_state TEXT NOT NULL CHECK(delivery_state='not_configured'),
                attempt_count INTEGER NOT NULL CHECK(attempt_count=0),
                created_at INTEGER NOT NULL,
                last_attempt_at INTEGER,
                authority_effect TEXT NOT NULL CHECK(authority_effect='none')
            );
            INSERT INTO notification_outbox SELECT notification_id,owner_digest,decision_id,proposal_id,kind,priority,delivery_state,attempt_count,created_at,last_attempt_at,authority_effect FROM notification_outbox_new;
            DROP TABLE notification_outbox_new;
            """
        )
        original._live.persist()
        reopened = ConversationStore(self.config, ISSUER, SUBJECT, notification_delivery_enabled=True)
        notification = reopened.list_notifications()["notifications"][0]
        self.assertEqual("not_configured", notification["delivery_state"])
        self.assertFalse(reopened.dispatch_one_notification(lambda _item: None, now=1_900_000_001, retry_seconds=900))

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

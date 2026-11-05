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
    def _record_decision(
        store: ConversationStore,
        suffix: str,
        *,
        expires_at: str = "2035-01-01T00:00:00Z",
    ) -> dict:
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
            json.dumps({
                "decision": "approved",
                "rationale": "Bounded notification-only test.",
                "expires_at": expires_at,
            }, separators=(",", ":")).encode(),
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
        with self.assertRaisesRegex(ConversationRequestError, "handoff_not_acknowledged"):
            store.record_cto_handoff_result(
                handoff["handoff_id"], "cto-result-handoff-0001", result_body,
                verified_cto_subject="auth0|approved-cto",
                expected_cto_subject="auth0|approved-cto",
            )
        with self.assertRaisesRegex(ConversationRequestError, "cto_identity_not_authorized"):
            store.acknowledge_cto_handoff(
                handoff["handoff_id"], "cto-acknowledgement-0001", b"{}",
                verified_cto_subject="auth0|wrong-cto",
                expected_cto_subject="auth0|approved-cto",
            )
        rollback_key = "cto-acknowledgement-rollback-0001"
        with patch.object(store._live, "persist", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                store.acknowledge_cto_handoff(
                    handoff["handoff_id"], rollback_key, b"{}",
                    verified_cto_subject="auth0|approved-cto",
                    expected_cto_subject="auth0|approved-cto",
                )
        self.assertEqual("awaiting_connector", store.list_cto_handoffs(conversation["conversation_id"])[0]["state"])
        self.assertNotIn("cto_handoff_acknowledged", [
            event["event_type"] for event in store.list_audit_timeline(conversation["conversation_id"])["events"]
        ])
        acknowledgement = store.acknowledge_cto_handoff(
            handoff["handoff_id"], rollback_key, b"{}",
            verified_cto_subject="auth0|approved-cto",
            expected_cto_subject="auth0|approved-cto",
        )
        self.assertFalse(acknowledgement["dispatch_authorized"])
        self.assertEqual(
            acknowledgement,
            store.acknowledge_cto_handoff(
                handoff["handoff_id"], rollback_key, b"{}",
                verified_cto_subject="auth0|approved-cto",
                expected_cto_subject="auth0|approved-cto",
            ),
        )
        self.assertEqual("acknowledged", store.list_cto_handoffs(conversation["conversation_id"])[0]["state"])
        self.assertEqual("acknowledged", self.store().list_cto_handoffs(conversation["conversation_id"])[0]["state"])
        with self.assertRaisesRegex(ConversationRequestError, "cto_acknowledgement_identity_mismatch"):
            store.record_cto_handoff_result(
                handoff["handoff_id"], "cto-result-other-identity-0001", result_body,
                verified_cto_subject="auth0|different-cto",
                expected_cto_subject="auth0|different-cto",
            )
        rollback_result_key = "cto-result-rollback-0001"
        with patch.object(store._live, "persist", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                store.record_cto_handoff_result(
                    handoff["handoff_id"], rollback_result_key, result_body,
                    verified_cto_subject="auth0|approved-cto",
                    expected_cto_subject="auth0|approved-cto",
                )
        self.assertEqual("acknowledged", store.list_cto_handoffs(conversation["conversation_id"])[0]["state"])
        self.assertEqual([], store.list_cto_handoff_results(conversation["conversation_id"]))
        self.assertNotIn("cto_handoff_result_recorded", [
            event["event_type"] for event in store.list_audit_timeline(conversation["conversation_id"])["events"]
        ])
        result = store.record_cto_handoff_result(
            handoff["handoff_id"], rollback_result_key, result_body,
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
                handoff["handoff_id"], rollback_result_key, result_body,
                verified_cto_subject="auth0|approved-cto",
                expected_cto_subject="auth0|approved-cto",
            ),
        )
        with self.assertRaisesRegex(ConversationRequestError, "cto_acknowledgement_identity_mismatch"):
            store.record_cto_handoff_result(
                handoff["handoff_id"], rollback_result_key, result_body,
                verified_cto_subject="auth0|different-cto",
                expected_cto_subject="auth0|different-cto",
            )
        self.assertEqual("result_recorded", store.list_cto_handoffs(conversation["conversation_id"])[0]["state"])
        with self.assertRaisesRegex(ConversationRequestError, "handoff_closed"):
            store.get_cto_handoff_packet(
                handoff["handoff_id"],
                verified_cto_subject="auth0|approved-cto",
                expected_cto_subject="auth0|approved-cto",
            )
        timeline = store.list_audit_timeline(conversation["conversation_id"])
        self.assertIn("cto_handoff_acknowledged", [event["event_type"] for event in timeline["events"]])
        self.assertIn("cto_handoff_result_recorded", [event["event_type"] for event in timeline["events"]])
        self.assertNotIn("Reviewed the bounded artifact.", json.dumps(timeline))

    def test_cto_handoff_expiry_after_packet_leaves_no_acknowledgement_or_result_receipt(self) -> None:
        now = 1_700_000_000
        with patch("conversation_store.time.time", return_value=now):
            store = self.store()
            decision = self._record_decision(
                store,
                "expiry-race",
                expires_at="2023-11-15T00:00:00Z",
            )
            handoff = store.create_cto_handoff(
                decision["proposal_id"], "handoff-expiry-race-0001", b"{}",
            )
            packet = store.get_cto_handoff_packet(
                handoff["handoff_id"],
                verified_cto_subject="auth0|approved-cto",
                expected_cto_subject="auth0|approved-cto",
            )
        self.assertEqual(handoff["handoff_id"], packet["handoff_id"])
        result_body = b'{"outcome":"completed","summary":"Not recorded after expiry.","evidence_refs":[]}'
        with patch("conversation_store.time.time", return_value=now + 10_000):
            with self.assertRaisesRegex(ConversationRequestError, "decision_expired"):
                store.acknowledge_cto_handoff(
                    handoff["handoff_id"], "cto-acknowledgement-expiry-race-0001", b"{}",
                    verified_cto_subject="auth0|approved-cto",
                    expected_cto_subject="auth0|approved-cto",
                )
            with self.assertRaisesRegex(ConversationRequestError, "decision_expired"):
                store.record_cto_handoff_result(
                    handoff["handoff_id"], "cto-result-expiry-race-0001", result_body,
                    verified_cto_subject="auth0|approved-cto",
                    expected_cto_subject="auth0|approved-cto",
                )
            self.assertEqual("awaiting_connector", store.list_cto_handoffs(handoff["conversation_id"])[0]["state"])
            self.assertEqual([], store.list_cto_handoff_results(handoff["conversation_id"]))
            timeline = store.list_audit_timeline(handoff["conversation_id"])
        self.assertNotIn("cto_handoff_acknowledged", [event["event_type"] for event in timeline["events"]])
        self.assertNotIn("cto_handoff_result_recorded", [event["event_type"] for event in timeline["events"]])
        receipt_count = store._live.connection.execute(
            "SELECT COUNT(*) FROM idempotency_results WHERE operation IN (?, ?)",
            (
                f"cto-acknowledgement:{handoff['handoff_id']}",
                f"cto-result:{handoff['handoff_id']}",
            ),
        ).fetchone()[0]
        self.assertEqual(0, receipt_count)

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


# Held-reference cleanup regressions are in the existing CI-invoked suite.
import itertools
import os
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import conversation_store as storage
import inquiry_persistence as persistence


def failures():
    return (None, RuntimeError("synthetic-private"), KeyboardInterrupt("synthetic-stop"), SystemExit(97))


class Resource:
    def __init__(self, failure=None):
        self.calls = 0
        self.failure = failure

    def close(self):
        self.calls += 1
        if self.failure is not None:
            raise self.failure


class CleanupChecks(unittest.TestCase):
    def capture(self, action):
        try:
            action()
        except BaseException as exc:
            return exc
        self.fail("failure was not raised")

    def expected(self, primary, cleanups):
        if primary is not None and not isinstance(primary, Exception):
            return primary
        return next((value for value in cleanups if value is not None and not isinstance(value, Exception)), primary)

    def test_connect_setup_and_cleanup_matrix(self):
        for primary, cleanup in itertools.product(failures()[1:], failures()):
            resource = Resource(cleanup)
            def execute(*_):
                raise primary
            resource.execute = execute
            with self.subTest(primary=type(primary).__name__, cleanup=type(cleanup).__name__), patch.object(storage.sqlite3, "connect", return_value=resource):
                observed = self.capture(storage._connect)
                self.assertIs(observed, self.expected(primary, (cleanup,)))
                self.assertEqual(resource.calls, 1)

    def test_snapshot_constructor_retirement_and_cleanup_matrix(self):
        for primary, cleanup in itertools.product(failures()[1:], failures()):
            resource = Resource(cleanup)
            held = storage.EncryptedSnapshot.__new__(storage.EncryptedSnapshot)
            def initialize(_):
                raise primary
            with self.subTest(primary=type(primary).__name__, cleanup=type(cleanup).__name__), patch.object(storage, "_connect", return_value=resource):
                observed = self.capture(lambda: held.__init__(Path(__file__).resolve().parent / "absent-synthetic-state", b"k" * 32, initialize))
                self.assertIs(observed, self.expected(primary, (cleanup,)))
                self.assertEqual(resource.calls, 1)
                self.assertIsNone(held.connection)

    def test_snapshot_source_cleanup_matrix_and_redaction(self):
        for primary, cleanup in itertools.product(failures(), failures()):
            if primary is None and cleanup is None:
                continue
            source = Resource(cleanup)
            source.deserialize = lambda _: None
            def backup(_):
                if primary is not None:
                    raise primary
            source.backup = backup
            held = storage.EncryptedSnapshot.__new__(storage.EncryptedSnapshot)
            held.connection = object()
            held.key = b"k" * 32
            crypto = SimpleNamespace(decrypt=lambda *_: b"synthetic")
            with self.subTest(primary=type(primary).__name__, cleanup=type(cleanup).__name__), patch.object(storage, "AESGCM", return_value=crypto), patch.object(storage.sqlite3, "connect", return_value=source):
                observed = self.capture(lambda: held._load(storage.MAGIC + b"n" * 12 + b"c" * 16))
                expected = self.expected(primary, (cleanup,))
                if expected is not None and not isinstance(expected, Exception):
                    self.assertIs(observed, expected)
                else:
                    self.assertIsInstance(observed, storage.ConversationConfigurationError)
                    self.assertEqual(str(observed), "conversation_snapshot_unavailable")
                    self.assertTrue(observed.__suppress_context__)
                self.assertEqual(source.calls, 1)

    def make_store(self, cleanup=(None, None, None)):
        held = storage.ConversationStore.__new__(storage.ConversationStore)
        held._lock = SimpleNamespace(raw=threading.Lock())
        held._closed = False
        resources = [Resource(value) for value in cleanup]
        held._live = SimpleNamespace(connection=resources[0])
        held._ledger = SimpleNamespace(connection=resources[1])
        held._lease = resources[2]
        return held, resources

    def test_store_close_all_resources_once_full_matrix(self):
        for cleanup in itertools.product(failures(), repeat=3):
            held, resources = self.make_store(cleanup)
            with self.subTest(kinds=[type(value).__name__ for value in cleanup]):
                if any(value is not None for value in cleanup):
                    observed = self.capture(held.close)
                    expected = self.expected(None, cleanup)
                    if expected is not None:
                        self.assertIs(observed, expected)
                    else:
                        self.assertIsInstance(observed, storage.ConversationConfigurationError)
                        self.assertEqual(str(observed), "conversation_store_close_unavailable")
                else:
                    held.close()
                self.assertEqual([resource.calls for resource in resources], [1, 1, 1])
                self.assertTrue(held._closed)
                self.assertIsNone(held._live)
                self.assertIsNone(held._ledger)
                self.assertIsNone(held._lease)
                held.close()
                self.assertEqual([resource.calls for resource in resources], [1, 1, 1])

    def test_store_constructor_failure_at_every_owned_stage(self):
        for stage, primary, cleanup in itertools.product(range(3), failures()[1:], failures()):
            lease = Resource(cleanup)
            connections = [Resource(cleanup), Resource(cleanup)]
            for connection in connections:
                connection.execute = lambda *_: SimpleNamespace(fetchone=lambda: None)
            snapshots = [SimpleNamespace(connection=connection) for connection in connections]
            outputs = iter(snapshots[:stage] + [primary])
            def snapshot(*_, **__):
                value = next(outputs)
                if isinstance(value, BaseException):
                    raise value
                return value
            held = storage.ConversationStore.__new__(storage.ConversationStore)
            config = storage.ConversationConfig(Path(__file__).resolve().parent / "live", Path(__file__).resolve().parent / "ledger", Path(__file__).resolve().parent / "key")
            with self.subTest(stage=stage, primary=type(primary).__name__, cleanup=type(cleanup).__name__), patch.object(storage, "load_key", return_value=b"k" * 32), patch.object(storage, "StoreLease", return_value=lease), patch.object(storage, "EncryptedSnapshot", side_effect=snapshot), patch.object(storage.ConversationStore, "_purge_locked", side_effect=primary):
                observed = self.capture(lambda: held.__init__(config, "https://accounts.google.com", "synthetic-owner"))
                self.assertIs(observed, self.expected(primary, (cleanup,)))
                self.assertEqual(lease.calls, 1)
                self.assertEqual([connection.calls for connection in connections], [int(stage >= 1), int(stage >= 2)])
                self.assertTrue(held._closed)
                held.close()
                self.assertEqual(lease.calls, 1)

    def test_lease_constructor_control_and_cleanup_matrix(self):
        for primary, cleanup in itertools.product(failures()[1:], failures()):
            held = persistence.StoreLease.__new__(persistence.StoreLease)
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
                opened = []
                closed = []
                real_open, real_close = os.open, os.close
                def acquire(*args, **kwargs):
                    descriptor = real_open(*args, **kwargs)
                    opened.append(descriptor)
                    return descriptor
                def release(descriptor):
                    closed.append(descriptor)
                    real_close(descriptor)
                    if cleanup is not None:
                        raise cleanup
                with self.subTest(primary=type(primary).__name__, cleanup=type(cleanup).__name__), patch.object(persistence.os, "open", side_effect=acquire), patch.object(persistence.os, "close", side_effect=release), patch.object(persistence.os, "fstat", side_effect=primary):
                    observed = self.capture(lambda: held.__init__(Path(temporary) / "state", exclusive=True))
                    expected = self.expected(primary, (cleanup,))
                    if not isinstance(expected, Exception):
                        self.assertIs(observed, expected)
                    else:
                        self.assertEqual(str(observed), "conversation_writer_unavailable")
                    self.assertEqual(closed, opened)
                    self.assertIsNone(held.fd)
                    held.close()
                    held.__del__()
                    self.assertEqual(closed, opened)

    def test_lease_uncertain_close_is_retired_without_retry(self):
        for cleanup in failures()[1:]:
            held = persistence.StoreLease.__new__(persistence.StoreLease)
            held.fd = 123456
            with patch.object(persistence.os, "close", side_effect=cleanup) as close:
                observed = self.capture(held.close)
                if isinstance(cleanup, Exception):
                    self.assertEqual(str(observed), "conversation_writer_unavailable")
                else:
                    self.assertIs(observed, cleanup)
                self.assertIsNone(held.fd)
                held.close()
                held.__del__()
                self.assertEqual(close.call_count, 1)

    def test_atomic_fdopen_failure_closes_descriptor_and_removes_temp(self):
        for primary, cleanup in itertools.product(failures()[1:], failures()):
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
                target = Path(temporary) / "state"
                closed = []
                real_close = os.close
                def close(descriptor):
                    closed.append(descriptor)
                    real_close(descriptor)
                    if cleanup is not None:
                        raise cleanup
                with self.subTest(primary=type(primary).__name__, cleanup=type(cleanup).__name__), patch.object(storage.os, "fdopen", side_effect=primary), patch.object(storage.os, "close", side_effect=close):
                    observed = self.capture(lambda: storage._atomic_write_private(target, b"synthetic", overwrite=True))
                    self.assertIs(observed, self.expected(primary, (cleanup,)))
                    self.assertEqual(len(closed), 1)
                self.assertEqual(list(target.parent.iterdir()), [])

    def test_atomic_unlink_cleanup_cannot_mask_primary_control(self):
        for primary, cleanup in itertools.product(failures()[1:], failures()[1:]):
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
                target = Path(temporary) / "state"
                with self.subTest(primary=type(primary).__name__, cleanup=type(cleanup).__name__), patch.object(storage.os, "fdopen", side_effect=primary), patch.object(Path, "unlink", side_effect=cleanup):
                    observed = self.capture(lambda: storage._atomic_write_private(target, b"synthetic", overwrite=True))
                    self.assertIs(observed, self.expected(primary, (cleanup,)))

    def test_real_store_round_trip_and_explicit_close_releases_lease(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            key = root / "key"
            key.write_text("22" * 32, encoding="ascii")
            os.chmod(key, 0o600)
            config = storage.ConversationConfig(root / "state", root / "ledger", key)
            held = storage.ConversationStore(config, "synthetic-issuer", "synthetic-owner")
            held.create_conversation("synthetic-roundtrip-key", b"{}")
            held.close()
            held.close()
            reopened = storage.ConversationStore(config, "synthetic-issuer", "synthetic-owner")
            self.assertEqual(reopened._live.connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 1)
            reopened.close()
            lease = persistence.StoreLease(config.state_file, exclusive=True)
            lease.close()



class IsolatedStorageChecks(unittest.TestCase):
    """Real FD contracts in the existing CI-invoked public storage suite."""
    def setUp(self):
        from dataclasses import replace
        import ruby_staging_isolated_store as isolated
        self.isolated=isolated
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o755)
        self.state=self.root/'state';self.state.mkdir(mode=0o700)
        self.keys=self.root/'keys';self.keys.mkdir()
        self.key=self.keys/'key.hex';self.key.write_text('73'*32);self.key.chmod(0o400)
        self.keys.chmod(0o555);self.addCleanup(lambda:self.keys.chmod(0o755))
        i=self.key.stat();d=self.state.stat();uid=os.geteuid();gid=os.getegid()
        self.policy=isolated.IsolatedStorePolicy('/state','/keys/key.hex',uid,gid,
            (('/',uid,gid,0o755),('/keys',uid,gid,0o555),('/state',uid,gid,0o700)),
            (d.st_dev,d.st_ino),(i.st_dev,i.st_ino,i.st_size,i.st_mtime_ns,i.st_ctime_ns),
            ('/production-excluded',),'synthetic-public-tests',True,True)
        self.real_open,self.real_close=os.open,os.close
        self.fds=set()
        protected={(p.stat().st_dev,p.stat().st_ino) for p in (self.key,self.keys)}
        def opening(path,flags,mode=0o777,*,dir_fd=None):
            actual=self.root if path=='/' and dir_fd is None else path
            fd=self.real_open(actual,flags,mode,**({} if dir_fd is None else {'dir_fd':dir_fd}))
            self.fds.add(fd);return fd
        def closing(fd):self.fds.discard(fd);return self.real_close(fd)
        def vfs(fd):
            details=os.fstat(fd)
            return SimpleNamespace(f_flag=os.ST_RDONLY if (details.st_dev,details.st_ino) in protected else 0)
        for guard in (patch('os.open',side_effect=opening),patch('os.close',side_effect=closing),patch('os.fstatvfs',side_effect=vfs)):
            guard.start();self.addCleanup(guard.stop)

    def test_static_policy_rejects_shared_overlap_or_incomplete_metadata_before_io(self):
        from dataclasses import replace
        for changes in ({'reader_uid':0},{'state_directory':'/keys/state'}, {'key_file':'/keys/../key.hex'},
                {'isolation_acknowledged':False},{'excluded_roots':()}, {'excluded_roots':('/state',)},
                {'directories':self.policy.directories[:-1]}, {'initialize_empty':'true'}):
            with patch('os.open',side_effect=AssertionError('policy touched path')):
                with self.assertRaises(self.isolated.IsolatedStoreConfigurationError):replace(self.policy,**changes).validate()
        self.assertEqual(self.fds,set())

    def test_actual_fd_key_lease_pair_write_read_close_and_restart(self):
        from dataclasses import replace
        files=self.isolated.IsolatedStoreFiles(self.policy)
        self.assertNotEqual(files.key,bytes.fromhex('73'*32))
        lease=files.acquire_lease();self.assertEqual(files.initial_pair(),(None,None))
        files.write(self.isolated.LEDGER,b'synthetic-ledger',overwrite=False)
        files.write(self.isolated.LIVE,b'synthetic-live',overwrite=False)
        self.assertEqual(files.read(self.isolated.LIVE,sync=True),b'synthetic-live')
        files.claim();files.close();files.close();self.assertIsNone(lease.fd);self.assertEqual(self.fds,set())
        files=self.isolated.IsolatedStoreFiles(replace(self.policy,initialize_empty=False))
        try:
            files.acquire_lease();self.assertEqual(files.initial_pair(),(b'synthetic-live',b'synthetic-ledger'))
        finally:files.close()
        self.assertEqual(self.fds,set())

    def test_bad_key_metadata_symlinks_and_missing_pair_fail_closed(self):
        from dataclasses import replace
        for changes in ({'key_identity':(0,)*5},{'state_identity':(0,0)}):
            with self.assertRaises(self.isolated.IsolatedStoreConfigurationError):self.isolated.IsolatedStoreFiles(replace(self.policy,**changes))
            self.assertEqual(self.fds,set())
        files=self.isolated.IsolatedStoreFiles(replace(self.policy,initialize_empty=False))
        try:
            files.acquire_lease()
            with self.assertRaises(self.isolated.IsolatedStoreConfigurationError):files.initial_pair()
            (self.state/self.isolated.LIVE).symlink_to(self.key)
            with self.assertRaises(self.isolated.IsolatedStoreConfigurationError):files.read(self.isolated.LIVE)
        finally:files.close()
        self.assertEqual(self.fds,set())

    def test_replaced_lock_and_uncertain_snapshot_write_fail_closed(self):
        files=self.isolated.IsolatedStoreFiles(self.policy);files.acquire_lease()
        try:
            for failure in (RuntimeError('private'),KeyboardInterrupt('private'),SystemExit(32)):
                with patch('os.replace',side_effect=failure):
                    expected=self.isolated.IsolatedStoreConfigurationError if isinstance(failure,Exception) else type(failure)
                    with self.assertRaises(expected):files.write(self.isolated.LIVE,b'synthetic')
                self.assertEqual(list(self.state.glob('.*.tmp')),[])
            (self.state/self.isolated.LOCK).unlink()
            (self.state/self.isolated.LOCK).touch(mode=0o600)
            with self.assertRaises(self.isolated.IsolatedStoreConfigurationError):files.read(self.isolated.LIVE,missing=True)
        finally:files.close()
        self.assertEqual(self.fds,set())


if __name__ == "__main__":
    unittest.main()

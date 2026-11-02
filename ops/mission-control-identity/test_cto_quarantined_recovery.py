"""Synthetic offline composition test; not live identity or recovery acceptance."""
import hashlib
import json
import os
import secrets
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from conversation_recovery import create_backup, restore_to_quarantine
from conversation_store import ConversationConfig, ConversationStore, ConversationRequestError, MAGIC
import test_conversation_store as fixtures

NOW = 1_900_000_000
ACTOR = dict(verified_cto_subject='auth0|synthetic-recovery-cto', expected_cto_subject='auth0|synthetic-recovery-cto')
ACK_KEY = 'recovery-acknowledgement-0001'
RESULT_KEY = 'recovery-result-key-0001'
BODY = b'{"outcome":"completed","summary":"Synthetic offline review.","evidence_refs":["review:synthetic-recovery"]}'


class CtoQuarantineRecoveryChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mc-cto-recovery-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        key = self.root / 'key'
        key.write_text(secrets.token_hex(32), encoding='ascii')
        key.chmod(0o600)
        self.config = ConversationConfig(self.root/'state.enc', self.root/'ledger.enc', key)
        self.stores = []
        self.addCleanup(self.close_stores)
        self.net = patch('socket.socket', side_effect=AssertionError('network forbidden'))
        self.socket = self.net.start()
        self.addCleanup(self.net.stop)
        self.clock = patch('conversation_store.time.time', return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def close_stores(self):
        for store in self.stores:
            store._live.connection.close()
            store._ledger.connection.close()
        self.stores.clear()

    def open_store(self, config):
        store = ConversationStore(config, fixtures.ISSUER, fixtures.SUBJECT)
        self.stores.append(store)
        return store

    def seed(self):
        store = self.open_store(self.config)
        expiry = datetime.fromtimestamp(NOW+120, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        decision = fixtures.ConversationStoreChecks._record_decision(store, 'recovery-only', expires_at=expiry)
        handoff = store.create_cto_handoff(decision['proposal_id'], 'recovery-handoff-key-0001', b'{}')
        return store, handoff

    def view(self, store, conversation):
        return {
            'handoffs': store.list_cto_handoffs(conversation),
            'results': store.list_cto_handoff_results(conversation),
            'audit': store.list_audit_timeline(conversation),
            'proposals': store.list_task_proposals(conversation),
            # Public summaries/old receipts do not prove the restored decision row.
            'decisions': [tuple(row) for row in store._live.connection.execute(
                'SELECT * FROM ceo_decisions ORDER BY decision_id')],
            'notifications': store.list_notifications(),
            'receipts': [tuple(row) for row in store._live.connection.execute(
                'SELECT * FROM idempotency_results ORDER BY operation,idempotency_hash')],
        }

    def restore(self, now):
        self.close_stores()  # No source writer remains active during backup.
        backup = self.root/'backup.enc'
        self.assertEqual(NOW, create_backup(self.config, backup, NOW))
        self.source_bytes = {p: p.read_bytes() for p in (self.config.state_file, self.config.deletion_ledger_file)}
        restored = ConversationConfig(self.root/'quarantine.enc', self.root/'quarantine-ledger.enc', self.config.key_file)
        self.assertEqual(NOW, restore_to_quarantine(self.config, backup, restored.state_file, restored.deletion_ledger_file, now))
        for p in (restored.state_file, restored.deletion_ledger_file):
            self.assertNotIn(p, self.source_bytes)
            self.assertEqual(self.root, p.parent)
            self.assertEqual(0o600, p.stat().st_mode & 0o777)
            self.assertTrue(p.read_bytes().startswith(MAGIC))
        return self.open_store(restored)

    def assert_unchanged_and_inert(self, store):
        for p, original in self.source_bytes.items():
            self.assertEqual(hashlib.sha256(original).digest(), hashlib.sha256(p.read_bytes()).digest())
        notifications = store.list_notifications()
        self.assertEqual('not_configured', notifications['transport_status'])
        self.assertTrue(all(x['attempt_count'] == 0 for x in notifications['notifications']))
        self.socket.assert_not_called()

    def test_completed_chain_survives_restore_without_duplicate_receipts_or_authority(self):
        store, h = self.seed()
        ack = store.acknowledge_cto_handoff(h['handoff_id'], ACK_KEY, b'{}', **ACTOR)
        result = store.record_cto_handoff_result(h['handoff_id'], RESULT_KEY, BODY, **ACTOR)
        before = self.view(store, h['conversation_id'])
        restored = self.restore(NOW)
        self.assertEqual(before, self.view(restored, h['conversation_id']))
        self.assertEqual('result_recorded', restored.list_cto_handoffs(h['conversation_id'])[0]['state'])
        self.assertEqual(ack, restored.acknowledge_cto_handoff(h['handoff_id'], ACK_KEY, b'{}', **ACTOR))
        self.assertEqual(result, restored.record_cto_handoff_result(h['handoff_id'], RESULT_KEY, BODY, **ACTOR))
        with self.assertRaisesRegex(ConversationRequestError, 'idempotency_conflict'):
            restored.record_cto_handoff_result(h['handoff_id'], RESULT_KEY, BODY.replace(b'offline', b'changed'), **ACTOR)
        with self.assertRaisesRegex(ConversationRequestError, 'cto_acknowledgement_identity_mismatch'):
            restored.record_cto_handoff_result(h['handoff_id'], 'recovery-other-key-0001', BODY,
                verified_cto_subject='auth0|different-synthetic', expected_cto_subject='auth0|different-synthetic')
        self.assertEqual(before, self.view(restored, h['conversation_id']))
        for response in (ack, result, *before['handoffs'], *before['results']):
            flags = {k:v for k,v in response.items() if k.endswith('_authorized')}
            self.assertTrue(flags)
            self.assertTrue(all(v is False for v in flags.values()))
        self.assertIs(ack['dispatch_authorized'], False)
        self.assertIs(result['execution_authorized'], False)
        self.assert_unchanged_and_inert(restored)

    def test_restored_awaiting_chain_still_rejects_expired_decision_without_consumption(self):
        store, h = self.seed()
        before = self.view(store, h['conversation_id'])
        with patch('conversation_store.time.time', return_value=NOW+121):
            restored = self.restore(NOW+121)
            self.assertEqual(before, self.view(restored, h['conversation_id']))
            for method, key, body in ((restored.acknowledge_cto_handoff, ACK_KEY, b'{}'),
                                       (restored.record_cto_handoff_result, RESULT_KEY, BODY)):
                with self.assertRaisesRegex(ConversationRequestError, 'decision_expired'):
                    method(h['handoff_id'], key, body, **ACTOR)
            self.assertEqual(before, self.view(restored, h['conversation_id']))
            self.assertEqual('awaiting_connector', restored.list_cto_handoffs(h['conversation_id'])[0]['state'])
            self.assert_unchanged_and_inert(restored)


if __name__ == '__main__':
    unittest.main()

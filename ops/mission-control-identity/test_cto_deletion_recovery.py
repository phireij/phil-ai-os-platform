"""Offline deleted-resource receipt suppression; inherits the two continuity checks."""
from unittest.mock import patch
import unittest

import test_cto_quarantined_recovery as baseline
from conversation_recovery import create_backup, restore_to_quarantine
from conversation_store import ConversationConfig, ConversationRequestError


class DeletedReceiptRecoveryChecks(baseline.CtoQuarantineRecoveryChecks):
    @staticmethod
    def receipts(store):
        return [tuple(row) for row in store._live.connection.execute(
            'SELECT * FROM idempotency_results ORDER BY operation,idempotency_hash')]

    def exercise_deleted_receipts(self, mode):
        store, handoff = self.seed()
        cid = handoff['conversation_id']
        store.acknowledge_cto_handoff(handoff['handoff_id'], baseline.ACK_KEY, b'{}', **baseline.ACTOR)
        store.record_cto_handoff_result(handoff['handoff_id'], baseline.RESULT_KEY, baseline.BODY, **baseline.ACTOR)
        other = store.create_conversation('unrelated-create-key-0001', b'{}')
        other_receipts = [r for r in self.receipts(store) if r[5] == other['conversation_id']]
        self.assertTrue(other_receipts)
        old_state = self.config.state_file.read_bytes()
        self.close_stores()
        backup = self.root/'before-deletion.enc'
        create_backup(self.config, backup, baseline.NOW)
        store = self.open_store(self.config)
        with patch('conversation_store.time.time', return_value=baseline.NOW+1):
            store.delete_conversation(cid)
        expected = self.receipts(store)
        expected_conversations = store.list_conversations()
        self.assertEqual([], [r for r in expected if r[5] == cid])
        self.assertEqual(other_receipts, [r for r in expected if r[5] == other['conversation_id']])
        self.close_stores()
        self.source_bytes = {p:p.read_bytes() for p in (self.config.state_file,self.config.deletion_ledger_file)}
        recovered = ConversationConfig(self.root/'replayed.enc',self.root/'replayed-ledger.enc',self.config.key_file)
        if mode == 'quarantine':
            restore_to_quarantine(self.config,backup,recovered.state_file,recovered.deletion_ledger_file,baseline.NOW+2)
        else:
            # Reproduce an interrupted deletion: old live snapshot + committed current ledger.
            recovered.state_file.write_bytes(old_state)
            recovered.deletion_ledger_file.write_bytes(self.config.deletion_ledger_file.read_bytes())
            recovered.state_file.chmod(0o600); recovered.deletion_ledger_file.chmod(0o600)
        with patch('conversation_store.time.time', return_value=baseline.NOW+2):
            restored = self.open_store(recovered)
            self.assertEqual(expected,self.receipts(restored))
            self.assertEqual(expected_conversations,restored.list_conversations())
            self.assertEqual(other,restored.create_conversation('unrelated-create-key-0001',b'{}'))
            with self.assertRaisesRegex(ConversationRequestError,'not_found'):
                restored.get_cto_handoff_packet(handoff['handoff_id'],**baseline.ACTOR)
            replacement = restored.create_conversation('create-notification-recovery-only',b'{}')
            self.assertNotEqual(cid,replacement['conversation_id'])
            self.assertEqual(2,len(restored.list_conversations()))
            self.assert_unchanged_and_inert(restored)

    def test_quarantine_does_not_resurrect_deleted_receipts_or_purge_unrelated(self):
        self.exercise_deleted_receipts('quarantine')

    def test_startup_replays_receipt_deletion_without_purging_unrelated(self):
        self.exercise_deleted_receipts('startup')


if __name__ == '__main__':
    unittest.main()

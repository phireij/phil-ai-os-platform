"""Synthetic source custody; no route, live data or authority activation."""
import copy
from dataclasses import replace
import hashlib
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

import conversation_store as core
from conversation_store import ConversationStore, ConversationRequestError
from ruby_inquiry import canonical, MAX_BODY, SOURCE_ENVELOPE, NO_AUTHORITY
import test_ruby_inquiry as inquiry_fixtures
from test_ruby_inquiry import CONTEXT, ISSUER, SUBJECT, POLICY, KEY, body, encoded

SOURCE_NOTE = 'SOURCE_ONLY_SENTINEL_原本'


def source():
    return {'synthetic_source': body(), 'source_note': SOURCE_NOTE}


def mapper(value, contact):
    if set(value) != {'synthetic_source', 'source_note'} or value['source_note'] != SOURCE_NOTE:
        raise ValueError('source invalid')
    result = value['synthetic_source']; result['contact'] = contact
    return result


class SourceCustodyChecks(unittest.TestCase):
    setUp = inquiry_fixtures.InquiryChecks.setUp
    tearDown = inquiry_fixtures.InquiryChecks.tearDown

    def open(self):
        self.policy = replace(self.policy, source_handoff_retention_enabled=True)
        return ConversationStore(self.config, ISSUER, SUBJECT,
            ruby_inquiry_policy=lambda c: self.policy, ruby_inquiry_source_mapper=mapper)

    def create(self, *, request=None, handoff=None, key=KEY):
        return self.store.create_ruby_inquiry(CONTEXT, key, encoded(body() if request is None else request),
            source_handoff_body=encoded(source() if handoff is None else handoff))

    def resolve(self):
        return self.store.resolve_ruby_inquiry_receipt(CONTEXT, 'create', KEY, encoded(body()), source_handoff_body=encoded(source()))

    def read(self, receipt):
        return self.store.get_ruby_inquiry_source(CONTEXT, receipt['receipt']['inquiry_id'], receipt['receipt']['revision_id'])

    def test_encrypted_roundtrip_no_default_exposure_and_retention(self):
        receipt = self.create(); detail = self.read(receipt)
        self.assertEqual(detail['source_handoff'], source())
        self.assertEqual(detail['source_fingerprint'], 'sha256:' + hashlib.sha256(canonical(source())).hexdigest())
        for k, v in NO_AUTHORITY.items(): self.assertEqual(detail[k], v)
        iid = receipt['receipt']['inquiry_id']
        for value in (receipt, self.resolve(), self.store.get_ruby_inquiry(CONTEXT, iid),
                      self.store.list_ruby_inquiries(CONTEXT), self.store.list_ruby_inquiry_audit(CONTEXT, iid)):
            self.assertNotIn(SOURCE_NOTE, json.dumps(value, ensure_ascii=False))
            self.assertNotIn('source_handoff', value); self.assertNotIn('source_fingerprint', value)
        self.assertNotIn(SOURCE_NOTE.encode(), self.config.state_file.read_bytes())
        self.store.close(); self.store = self.open()
        self.assertEqual(self.resolve(), receipt); self.assertEqual(self.read(receipt), detail)
        self.store._purge_locked(100 * 365 * 24 * 3600)
        self.assertEqual(self.read(receipt), detail)

    def test_legacy_fingerprint_unchanged_and_explicit_absence(self):
        request = body(); receipt = self.store.create_ruby_inquiry(CONTEXT, KEY, encoded(request))
        self.assertEqual(receipt['receipt']['request_fingerprint'], 'sha256:' + hashlib.sha256(canonical(request)).hexdigest())
        with self.assertRaisesRegex(ConversationRequestError, 'source_unavailable'): self.read(receipt)
        with self.assertRaisesRegex(ConversationRequestError, 'idempotency_conflict'): self.create()
        self.assertEqual(self.store.create_ruby_inquiry(CONTEXT, KEY, encoded(request)), receipt)

    def test_canonical_equivalence_but_presence_and_changes_conflict(self):
        receipt = self.create()
        equivalent = json.dumps(source(), ensure_ascii=True, indent=2, sort_keys=True).encode()
        self.assertEqual(self.store.create_ruby_inquiry(CONTEXT, KEY, encoded(body()), source_handoff_body=equivalent), receipt)
        for attempt in (None, encoded({**source(), 'source_note': 'different'})):
            with self.assertRaisesRegex(ConversationRequestError, 'idempotency_conflict'):
                self.store.create_ruby_inquiry(CONTEXT, KEY, encoded(body()), source_handoff_body=attempt)
        changed = body(); changed['fulfillment']['requested_date'] = '2028-03-02'
        with self.assertRaisesRegex(ConversationRequestError, 'idempotency_conflict'): self.create(request=changed)

    def test_mapper_exact_equality_detachment_errors_and_strict_result(self):
        changed = body(); changed['customization']['custom_notes'] += ' DIFFERENT'
        with self.assertRaisesRegex(ConversationRequestError, 'source_mismatch'): self.create(request=changed)
        for callback in (lambda *a: True, lambda *a: 1, lambda *a: None,
                         lambda *a: (_ for _ in ()).throw(RuntimeError(SOURCE_NOTE))):
            with patch.object(self.store, '_ruby_inquiry_source_mapper', callback):
                with self.assertRaisesRegex(ConversationRequestError, 'source_mismatch') as caught: self.create()
                self.assertNotIn(SOURCE_NOTE, str(caught.exception))
        original = source()
        def mutating(src, contact):
            src['source_note'] = 'CHANGED'; contact['destination'] = 'different@example.invalid'
            return body()
        with patch.object(self.store, '_ruby_inquiry_source_mapper', mutating): receipt = self.create(handoff=original)
        self.assertEqual(self.read(receipt)['source_handoff'], original)

    def test_policy_mapper_owner_scope_and_current_revision(self):
        for flag in (False, 1, 'true', None):
            self.policy = replace(self.policy, source_handoff_retention_enabled=flag)
            with self.assertRaisesRegex(ConversationRequestError, 'source_policy_unavailable'): self.create()
        self.policy = replace(self.policy, source_handoff_retention_enabled=True); receipt = self.create()
        iid, rid = receipt['receipt']['inquiry_id'], receipt['receipt']['revision_id']
        for value in (None, False, 'mapper'):
            with patch.object(self.store, '_ruby_inquiry_source_mapper', value):
                with self.assertRaisesRegex(ConversationRequestError, 'source_policy_unavailable'): self.read(receipt)
        for field in ('subject', 'issuer', 'project_id', 'source_system', 'source_instance'):
            with self.assertRaises(ConversationRequestError):
                self.store.get_ruby_inquiry_source(replace(CONTEXT, **{field:'other'}), iid, rid)
        for value in (None, True, '', 'unknown-revision-0001'):
            with self.assertRaisesRegex(ConversationRequestError, 'stale_revision'):
                self.store.get_ruby_inquiry_source(CONTEXT, iid, value)
        with self.assertRaisesRegex(ConversationRequestError, 'not_found'):
            self.store.get_ruby_inquiry_source(CONTEXT, 'unknown-inquiry-00001', rid)
        self.policy = replace(self.policy, source_handoff_retention_enabled=False)
        with self.assertRaisesRegex(ConversationRequestError, 'source_policy_unavailable'): self.read(receipt)
        self.assertEqual(self.store.get_ruby_inquiry(CONTEXT, iid)['inquiry'], body())

    def test_revision_source_no_downgrade_stale_fallback_or_inheritance(self):
        first = self.create(); iid, rid = first['receipt']['inquiry_id'], first['receipt']['revision_id']
        changed = body(); changed['fulfillment']['requested_date'] = '2028-03-02'
        revised_source = source(); revised_source['synthetic_source'] = changed
        request = {'expected_revision_id': rid, 'inquiry': changed}
        with self.assertRaisesRegex(ConversationRequestError, 'source_required'):
            self.store.revise_ruby_inquiry(CONTEXT, iid, 'synthetic-revision-key', encoded(request))
        second = self.store.revise_ruby_inquiry(CONTEXT, iid, 'synthetic-revision-key', encoded(request), source_handoff_body=encoded(revised_source))
        self.assertEqual(self.read(second)['source_handoff'], revised_source)
        self.assertEqual(self.store.get_ruby_inquiry(CONTEXT, iid)['inquiry'], changed)
        with self.assertRaisesRegex(ConversationRequestError, 'stale_revision'): self.read(first)
        self.assertEqual(self.resolve(), first)
        self.assertEqual(self.store.resolve_ruby_inquiry_receipt(CONTEXT, 'revise', 'synthetic-revision-key', encoded(request), inquiry_id=iid, source_handoff_body=encoded(revised_source)), second)

    def test_new_writes_use_current_catalog_replay_and_read_do_not_reprice(self):
        receipt = self.create()
        self.policy = replace(self.policy, catalog_revision='new-catalog', catalog_prices=(('CAKE-A', 9999),))
        with patch.object(self.store, '_ruby_inquiry_source_mapper', side_effect=AssertionError('must not reprice')):
            self.assertEqual(self.resolve(), receipt); self.assertEqual(self.create(), receipt)
            self.assertEqual(self.read(receipt)['source_handoff'], source())
            with self.assertRaisesRegex(ConversationRequestError, 'catalog_conflict'): self.create(key='different-source-key')

    def test_combined_bounds_strict_json_and_internal_envelope_not_wire_format(self):
        invalid = [b'', b'null', b'[]', b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff',
                   b'{"x":"\\ud800"}', b'{"x":1.5}', b'{"x":9007199254740992}',
                   b'{"x":'+b'['*17+b'0'+b']'*17+b'}', b' '* (MAX_BODY+1),
                   encoded({'x':[None]*8192}), encoded({'x':'x'*(MAX_BODY-100)})]
        for value in invalid:
            with self.subTest(source=value[:40]), self.assertRaises(ConversationRequestError):
                self.store.create_ruby_inquiry(CONTEXT, KEY, encoded(body()), source_handoff_body=value)
        envelope = {'schema_version': SOURCE_ENVELOPE, 'request': body(), 'source_handoff': source()}
        with self.assertRaisesRegex(ConversationRequestError, 'source_invalid'):
            self.store.create_ruby_inquiry(CONTEXT, KEY, encoded(envelope))

    def test_corrupt_or_missing_evidence_no_reconstruction(self):
        receipt = self.create(); connection = self.store._live.connection; saved = connection.serialize()
        for statement in ('DELETE FROM ruby_custom_inquiry_receipts', 'DELETE FROM ruby_custom_inquiry_audit',
                          'DELETE FROM ruby_custom_inquiry_audit; DELETE FROM ruby_custom_inquiry_revisions',
                          "UPDATE ruby_custom_inquiry_revisions SET request_json='{}'",
                          "UPDATE ruby_custom_inquiry_revisions SET prior_revision_id='wrong'",
                          "UPDATE ruby_custom_inquiry_receipts SET response_json='{}'",
                          "UPDATE ruby_custom_inquiry_audit SET policy_version='wrong'"):
            with self.subTest(statement=statement):
                connection.deserialize(saved); connection.executescript(statement); damaged = connection.serialize()
                with self.assertRaises(ConversationRequestError): self.read(receipt)
                self.assertEqual(connection.serialize(), damaged)
        connection.deserialize(saved); connection.execute('DELETE FROM ruby_custom_inquiry_receipts')
        self.assertEqual(self.create()['state'], 'unknown'); self.assertEqual(self.resolve()['state'], 'unknown')
        with self.assertRaisesRegex(ConversationRequestError, 'idempotency_conflict'):
            self.create(handoff={**source(), 'source_note':'changed'})
        self.assertEqual(len(self.store.list_ruby_inquiries(CONTEXT)['inquiries']), 1)

    def test_sql_failures_roll_back_all_source_and_evidence(self):
        before = self.config.state_file.read_bytes()
        for stage in ('pointer', 'detail', 'audit', 'receipt'):
            def fail(current):
                if current == stage: raise RuntimeError(SOURCE_NOTE)
            with patch.object(self.store, '_inquiry_stage', side_effect=fail):
                with self.assertRaisesRegex(ConversationRequestError, 'write_failed'): self.create()
            self.assertEqual(self.config.state_file.read_bytes(), before)
            self.assertEqual(self.store.list_ruby_inquiries(CONTEXT)['inquiries'], [])
            self.assertEqual(self.resolve()['state'], 'unknown')

    def test_before_after_replace_uncertainty_fences_and_recovers_exact_source(self):
        before = self.config.state_file.read_bytes()
        with patch.object(core.os, 'replace', side_effect=OSError(SOURCE_NOTE)):
            with self.assertRaisesRegex(ConversationRequestError, 'outcome_unknown'): self.create()
        with self.assertRaisesRegex(ConversationRequestError, 'fenced'):
            self.store.get_ruby_inquiry_source(CONTEXT, 'unknown-inquiry-00001', 'unknown-revision-0001')
        self.assertEqual(self.config.state_file.read_bytes(), before)
        self.store.reconcile_persistence(ISSUER, SUBJECT, inquiry_context=CONTEXT)
        self.assertEqual(self.resolve()['state'], 'unknown')
        original = core.os.replace
        def fail_after(source_path, target):
            original(source_path, target)
            if target == self.config.state_file: raise OSError(SOURCE_NOTE)
        with patch.object(core.os, 'replace', side_effect=fail_after):
            with self.assertRaisesRegex(ConversationRequestError, 'outcome_unknown'): self.create()
        self.store.reconcile_persistence(ISSUER, SUBJECT, inquiry_context=CONTEXT)
        receipt = self.resolve(); self.assertEqual(self.read(receipt)['source_handoff'], source())
        self.assertEqual(self.create(), receipt)

    def test_new_process_restart_reads_exact_source(self):
        receipt = self.create(); self.store.close()
        script = '''import json,sys
from pathlib import Path
from conversation_store import ConversationConfig,ConversationStore
from test_ruby_inquiry import CONTEXT,ISSUER,SUBJECT,POLICY,KEY,body,encoded
from test_ruby_inquiry_source import mapper,source
from dataclasses import replace
p=Path(sys.argv[1])
s=ConversationStore(ConversationConfig(p/'state.enc',p/'ledger.enc',p/'synthetic.key'),ISSUER,SUBJECT,ruby_inquiry_policy=lambda c:replace(POLICY,source_handoff_retention_enabled=True),ruby_inquiry_source_mapper=mapper)
r=s.resolve_ruby_inquiry_receipt(CONTEXT,'create',KEY,encoded(body()),source_handoff_body=encoded(source()))
assert s.get_ruby_inquiry_source(CONTEXT,r['receipt']['inquiry_id'],r['receipt']['revision_id'])['source_handoff']==source()
print(json.dumps(r));s.close()
'''
        result = subprocess.run([sys.executable, '-B', '-c', script, str(self.root)], cwd=os.path.dirname(__file__), capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), receipt); self.store = self.open()

    def test_actual_process_crash_before_and_after_replace(self):
        self.store.close()
        script = r'''import os,sys
from pathlib import Path
import conversation_store as core
from conversation_store import ConversationConfig,ConversationStore
from test_ruby_inquiry import CONTEXT,ISSUER,SUBJECT,POLICY,body,encoded
from test_ruby_inquiry_source import mapper,source
from dataclasses import replace
p=Path(sys.argv[1]);phase=sys.argv[2]
s=ConversationStore(ConversationConfig(p/'state.enc',p/'ledger.enc',p/'synthetic.key'),ISSUER,SUBJECT,ruby_inquiry_policy=lambda c:replace(POLICY,source_handoff_retention_enabled=True),ruby_inquiry_source_mapper=mapper)
original=core.os.replace
def crash(a,b):
 if b==p/'state.enc' and phase=='before':os._exit(73)
 original(a,b)
 if b==p/'state.enc':os._exit(74)
core.os.replace=crash
s.create_ruby_inquiry(CONTEXT,'source-process-crash-'+phase,encoded(body()),source_handoff_body=encoded(source()))
raise AssertionError('receipt cannot return')
'''
        for phase, code in (('before',73),('after',74)):
            result = subprocess.run([sys.executable, '-B', '-c', script, str(self.root), phase], cwd=os.path.dirname(__file__), capture_output=True)
            self.assertEqual(result.returncode, code, result.stderr)
            self.store = self.open()
            receipt = self.store.resolve_ruby_inquiry_receipt(CONTEXT, 'create', 'source-process-crash-'+phase, encoded(body()), source_handoff_body=encoded(source()))
            self.assertEqual(receipt['state'], 'unknown' if phase=='before' else 'complete_received')
            if phase=='after': self.assertEqual(self.read(receipt)['source_handoff'],source())
            self.store.close()
        self.store = self.open()
        self.assertEqual(len(self.store.list_ruby_inquiries(CONTEXT)['inquiries']),1)

    def test_explicit_legacy_revision_upgrade(self):
        old = self.store.create_ruby_inquiry(CONTEXT, KEY, encoded(body()))
        iid, rid = old['receipt']['inquiry_id'], old['receipt']['revision_id']
        new = self.store.revise_ruby_inquiry(CONTEXT, iid, 'explicit-source-revision', encoded({'expected_revision_id':rid,'inquiry':body()}), source_handoff_body=encoded(source()))
        self.assertEqual(self.read(new)['source_handoff'], source())
        self.assertEqual(self.store.resolve_ruby_inquiry_receipt(CONTEXT, 'create', KEY, encoded(body())), old)
        with self.assertRaisesRegex(ConversationRequestError, 'stale_revision'): self.read(old)

if __name__ == '__main__': unittest.main()

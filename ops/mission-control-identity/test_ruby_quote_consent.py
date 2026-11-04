"""Disposable synthetic consent projection/binding checks; no real identities."""
import copy
import hashlib
import json
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import test_ruby_quote_custody as fixtures
from conversation_store import ConversationStore, ConversationRequestError, ConversationConfigurationError
from test_ruby_inquiry import CONTEXT, ISSUER, SUBJECT, body, encoded
from ruby_inquiry import canonical
from ruby_quote_custody import BOUND_RESPONSE_SCHEMA, fingerprint


class QuoteConsentChecks(unittest.TestCase):
    setUp = fixtures.CustodyChecks.setUp
    tearDown = fixtures.CustodyChecks.tearDown
    create = fixtures.CustodyChecks.create
    setup_offer = fixtures.CustodyChecks.setup_offer
    record = fixtures.CustodyChecks.record
    resolve = fixtures.CustodyChecks.resolve
    counts = fixtures.CustodyChecks.counts
    view = fixtures.CustodyChecks.view
    withdrawal = fixtures.CustodyChecks.withdrawal
    next_quote = fixtures.CustodyChecks.next_quote

    def open(self):
        return ConversationStore(self.config, ISSUER, SUBJECT,
            ruby_inquiry_policy=lambda c: replace(self.policy, finalized_quotes_enabled=True,
                quote_custody_enabled=True, quote_consent_enabled=True) if self.policy else None,
            ruby_finalized_quotes_enabled=True, ruby_quote_custody_enabled=True,
            ruby_quote_consent_enabled=True, ruby_quote_synthetic_verifier=fixtures.verifier)

    def context(self):
        return self.store.get_ruby_quote_response_context(CONTEXT, self.iid)

    def bound(self):
        context = self.context()
        return {**self.response, 'schema_version': BOUND_RESPONSE_SCHEMA,
                'selection_fingerprint': context['selection_fingerprint']}

    def assert_inert(self, value):
        for key, expected in fixtures.NO_QUOTE_AUTHORITY.items():
            self.assertEqual(value[key], expected)
        self.assertIs(value['customer_identity_verified'], False)
        self.assertIs(value['current_quote_verified'], False)

    def test_selected_projection_exact_consent_snapshot_without_writes(self):
        self.setup_offer(); before = self.config.state_file.read_bytes(); counts = self.counts()
        context = self.context()
        self.assertEqual(context['consent_text'], fixtures.CONSENT)
        self.assertEqual(context['binding']['selected_event_id'], self.selected['event_id'])
        self.assertEqual(context['binding']['consent_fingerprint'], fingerprint(fixtures.CONSENT.encode()))
        self.assertEqual(context['selection_fingerprint'], fingerprint(canonical(context['binding'])))
        self.assertEqual(context['quote_snapshot']['quote'], self.quote_body)
        self.assertEqual(context['inquiry_revision_id'], self.quote_body['expected_revision_id'])
        self.assertEqual(self.counts(), counts); self.assertEqual(self.config.state_file.read_bytes(), before)
        self.assert_inert(context)

    def test_fresh_process_retrieves_retained_consent_without_original_selection_request(self):
        self.setup_offer(); expected = self.context(); self.store.close()
        script = '''
import json,sys
from pathlib import Path
from dataclasses import replace
from conversation_store import ConversationConfig,ConversationStore
from test_ruby_inquiry import ISSUER,SUBJECT,POLICY,CONTEXT
from test_ruby_quote_custody import verifier
root=Path(sys.argv[1])
s=ConversationStore(ConversationConfig(root/'state.enc',root/'ledger.enc',root/'synthetic.key'),ISSUER,SUBJECT,ruby_inquiry_policy=lambda c:replace(POLICY,finalized_quotes_enabled=True,quote_custody_enabled=True,quote_consent_enabled=True),ruby_finalized_quotes_enabled=True,ruby_quote_custody_enabled=True,ruby_quote_consent_enabled=True,ruby_quote_synthetic_verifier=verifier)
print(json.dumps(s.get_ruby_quote_response_context(CONTEXT,sys.argv[2])))
s.close()
'''
        run = subprocess.run([sys.executable, '-B', '-c', script, str(self.root), self.iid],
            cwd=Path(__file__).parent, text=True, capture_output=True, timeout=30, check=True)
        self.assertEqual(json.loads(run.stdout), expected); self.store = self.open()

    def test_bound_response_roundtrip_restart_recovery_and_legacy_key_conflict(self):
        self.setup_offer(); request = self.bound(); result = self.record(request)
        self.assertEqual(self.record(request), result); self.assertEqual(self.resolve(request), result)
        with self.assertRaisesRegex(ConversationRequestError, 'idempotency_conflict'):
            self.record(self.response)
        self.store.close(); self.store = self.open()
        self.assertEqual(self.resolve(request), result)
        self.assertEqual(self.context()['state'], 'already_responded')
        self.assert_inert(result); self.assertEqual(self.counts(), (2,2,2,1))

    def test_constructor_and_policy_gates_default_off(self):
        self.setup_offer(); request = self.bound(); before = self.counts()
        self.store._ruby_quote_consent_enabled = False
        for action in (self.context, lambda: self.record(request), lambda: self.resolve(request)):
            with self.assertRaisesRegex(ConversationRequestError, 'quote_consent_policy_unavailable'): action()
        self.assertEqual(self.counts(), before)
        self.store._ruby_quote_consent_enabled = True
        self.store._ruby_inquiry_policy = lambda c: replace(self.policy,finalized_quotes_enabled=True,quote_custody_enabled=True)
        with self.assertRaisesRegex(ConversationRequestError, 'quote_consent_policy_unavailable'): self.context()
        self.store.close()
        self.store = ConversationStore(self.config,ISSUER,SUBJECT,
            ruby_inquiry_policy=lambda c: replace(self.policy,finalized_quotes_enabled=True,quote_custody_enabled=True,quote_consent_enabled=True),
            ruby_finalized_quotes_enabled=True,ruby_quote_custody_enabled=True,ruby_quote_synthetic_verifier=fixtures.verifier)
        with self.assertRaisesRegex(ConversationRequestError, 'quote_consent_policy_unavailable'): self.context()

    def test_constructor_strict_boolean_and_existing_synthetic_dependency(self):
        self.store.close()
        for flag in (1, 0, 'true', None, True):
            with self.subTest(flag=flag):
                with self.assertRaisesRegex(ConversationConfigurationError, 'quote_consent_synthetic_mode_required'):
                    ConversationStore(self.config,ISSUER,SUBJECT,ruby_quote_consent_enabled=flag)
        self.store = self.open()

    def test_no_selection_unknown_and_closed_offers_do_not_return_consent(self):
        inquiry = self.create()['receipt']; self.iid = inquiry['inquiry_id']
        self.assertEqual(self.context()['state'], 'unknown')
        self.store.close(); self.temp.cleanup(); self.setUp(); self.setup_offer()
        self.record(self.withdrawal(self.selected['event_id']), 'synthetic-withdraw-consent01')
        result = self.context(); self.assertEqual(result['state'], 'withdrawn')
        self.assertNotIn('consent_text',result);self.assertNotIn('quote_snapshot',result)
        self.assert_inert(result)

    def test_decline_and_accept_have_no_fresh_response_context(self):
        self.setup_offer(); request=self.bound();request['decision']='decline';self.record(request)
        result=self.context();self.assertEqual(result['state'],'already_responded')
        self.assertNotIn('consent_text',result);self.assert_inert(result)

    def test_inquiry_revision_stales_context_and_frozen_bound_request(self):
        self.setup_offer();request=self.bound();changed=body();changed['customization']['custom_notes']='Changed synthetic scope'
        self.store.revise_ruby_inquiry(CONTEXT,self.iid,'synthetic-consent-revision01',encoded({'expected_revision_id':self.quote_body['expected_revision_id'],'inquiry':changed}))
        result=self.context();self.assertEqual(result['state'],'stale_inquiry_revision');self.assertNotIn('consent_text',result)
        with self.assertRaisesRegex(ConversationRequestError,'stale_revision'):self.record(request)

    def test_bound_event_and_consent_mutations_fail_without_writes(self):
        self.setup_offer();request=self.bound();before=self.counts()
        for key,value in (('selection_fingerprint','sha256:'+'0'*64),('consent_fingerprint','sha256:'+'1'*64),('quote_fingerprint','sha256:'+'2'*64),('expected_event_id','synthetic-other-event-0001'),('customer_accepted',True)):
            with self.subTest(key=key):
                with self.assertRaises(ConversationRequestError):self.record(dict(request,**{key:value}))
        self.assertEqual(self.counts(),before)

    def test_v1_selection_cannot_claim_new_bound_response_schema(self):
        self.setup_offer();before=self.counts()
        for request in (dict(self.selection,schema_version=BOUND_RESPONSE_SCHEMA),dict(self.response,selection_fingerprint='sha256:'+'0'*64)):
            with self.assertRaises(ConversationRequestError):self.record(request)
        self.assertEqual(self.counts(),before)

    def test_withdraw_and_replace_reject_frozen_response(self):
        self.setup_offer();request=self.bound()
        self.record(self.withdrawal(self.selected['event_id']),'synthetic-withdraw-binding01')
        with self.assertRaisesRegex(ConversationRequestError,'stale_quote_custody'):self.record(request)
        quote,selection=self.next_quote(self.view()['event_id']);self.record(selection,'synthetic-reselect-binding02')
        fresh=self.context();self.assertEqual(fresh['binding']['quote_id'],quote['quote_id'])
        with self.assertRaisesRegex(ConversationRequestError,'stale_quote_custody'):self.record(request)
        request['expected_event_id']=fresh['binding']['selected_event_id']
        with self.assertRaisesRegex(ConversationRequestError,'quote_not_current'):self.record(request)

    def test_missing_history_and_source_dependencies_fail_closed(self):
        self.setup_offer();self.store._live.connection.execute('DELETE FROM ruby_quote_custody_audit')
        self.assertEqual(self.context()['state'],'unknown')
        self.store.close();self.temp.cleanup();self.setUp();self.setup_offer()
        self.store._live.connection.execute('DELETE FROM ruby_finalized_quote_receipts')
        result=self.context();self.assertEqual(result['state'],'unknown');self.assertNotIn('consent_text',result)

    def test_current_policy_and_context_isolation(self):
        self.setup_offer()
        for context in (replace(CONTEXT,source_instance='other'),replace(CONTEXT,project_id='other')):
            with self.assertRaises(ConversationRequestError):self.store.get_ruby_quote_response_context(context,self.iid)
        self.policy=None
        with self.assertRaisesRegex(ConversationRequestError,'inquiry_policy_unavailable'):self.context()

    def test_replay_validates_bound_semantics_not_just_consistent_row_hashes(self):
        self.setup_offer();request=self.bound();receipt=self.record(request)
        bad=dict(request,selection_fingerprint='sha256:'+'f'*64);hashed=hashlib.sha256(canonical(bad)).digest()
        changed=dict(receipt,request_fingerprint='sha256:'+hashed.hex())
        c=self.store._live.connection
        c.execute('UPDATE ruby_quote_custody_events SET request_json=?, request_hash=? WHERE event_id=?',(canonical(bad).decode(),hashed,receipt['event_id']))
        c.execute('UPDATE ruby_quote_custody_receipts SET request_hash=?,response_json=? WHERE event_id=?',(hashed,canonical(changed).decode(),receipt['event_id']))
        c.execute('UPDATE ruby_quote_custody_audit SET request_hash=? WHERE event_id=?',(hashed,receipt['event_id']))
        for action in (self.view,self.context,lambda:self.resolve(bad)):
            with self.assertRaisesRegex(ConversationRequestError,'quote_custody_binding_mismatch'):action()

    def test_missing_superseded_source_does_not_hide_independent_current_offer(self):
        self.setup_offer();request=self.bound();old=self.record(request)
        new_quote,selected=self.next_quote(old['event_id']);self.record(selected,'synthetic-next-bound-select02')
        self.store._live.connection.execute('DELETE FROM ruby_finalized_quote_audit WHERE quote_id=?',(self.quote_receipt['quote_id'],))
        self.assertEqual(self.resolve(request)['state'],'unknown')
        self.assertEqual(self.context()['binding']['quote_id'],new_quote['quote_id'])

    def test_uncertain_append_fenced_then_original_receipt_recovered(self):
        self.setup_offer();request=self.bound();persist=self.store._live.persist
        def fail():persist();raise OSError('synthetic lost response')
        with patch.object(self.store._live,'persist',fail):
            with self.assertRaisesRegex(ConversationRequestError,'quote_custody_outcome_unknown'):self.record(request)
        with self.assertRaisesRegex(ConversationRequestError,'conversation_store_fenced'):self.context()
        self.store.reconcile_persistence(ISSUER,SUBJECT,inquiry_context=CONTEXT)
        self.assertEqual(self.record(request),self.resolve(request));self.assertEqual(self.counts(),(2,2,2,1))

    def test_bound_receipt_recovery_does_not_require_live_verifier(self):
        self.setup_offer();request=self.bound();original=self.record(request)
        self.store._ruby_quote_synthetic_verifier=lambda *args:1/0
        self.assertEqual(self.resolve(request),original)
        with self.assertRaisesRegex(ConversationRequestError,'synthetic_verification_unavailable'):self.record(request)

    def test_exact_unicode_and_whitespace_consent_not_normalized(self):
        self.setup_offer();original=self.record(self.bound())
        new_quote,selected=self.next_quote(original['event_id'])
        selected['consent_text']='  SYNTHETIC 予約 e\u0301\n\t同意のみ  '
        self.record(selected,'synthetic-unicode-select02');context=self.context()
        self.assertEqual(context['consent_text'],selected['consent_text'])
        self.assertEqual(context['binding']['consent_fingerprint'],fingerprint(selected['consent_text'].encode('utf-8')))
        self.assertNotEqual(context['binding']['consent_fingerprint'],fingerprint(selected['consent_text'].strip().encode('utf-8')))

    def test_projection_and_returned_requests_do_not_mutate_retained_evidence(self):
        self.setup_offer();before=self.context();mutated=self.context()
        mutated['consent_text']='Changed';mutated['binding']['quote_fingerprint']='sha256:'+'0'*64
        mutated['quote_snapshot']['quote']['items'][0]['description']='Changed'
        self.assertEqual(self.context(),before)


if __name__=='__main__':unittest.main()

"""Disposable local synthetic-only quote custody acceptance checks."""
import copy
import json
import os
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from test_ruby_inquiry import InquiryChecks, POLICY, CONTEXT, ISSUER, SUBJECT, body, encoded
from conversation_store import ConversationStore, ConversationRequestError, ConversationConfigurationError
from ruby_finalized_quote import SCHEMA, NO_QUOTE_AUTHORITY

QUOTE_KEY = "synthetic-quote-idempotency-0001"

def quote(revision):
    return {"schema_version": SCHEMA, "expected_revision_id": revision, "source_quote_ref": "synthetic-quote-1", "currency": "JPY",
        "items": [{"line_ref": "cake", "description": "Synthetic custom cake", "quantity": 2, "unit_price_yen": 3100, "line_total_yen": 6200}],
        "shipping_yen": 0, "total_yen": 6200,
        "fulfillment": {"method": "pickup", "date": "2028-02-29", "time_window": "14:30", "packing_plan_ref": "synthetic-plan-unverified"}}


class QuoteChecks(InquiryChecks):
    # Base inquiry tests remain useful against the extension; explicit opt-in here.
    def open(self):
        return ConversationStore(self.config, ISSUER, SUBJECT, ruby_inquiry_policy=lambda c: replace(self.policy, finalized_quotes_enabled=True) if self.policy else None, ruby_finalized_quotes_enabled=True)

    def setup_quote(self):
        self.inquiry_receipt = self.create()
        self.iid = self.inquiry_receipt["receipt"]["inquiry_id"]
        self.value = quote(self.inquiry_receipt["receipt"]["revision_id"])

    def record(self, value=None, key=QUOTE_KEY, context=CONTEXT):
        return self.store.record_ruby_finalized_quote(context, self.iid, key, encoded(self.value if value is None else value))

    def resolve_quote(self, value=None, key=QUOTE_KEY, context=CONTEXT):
        return self.store.resolve_ruby_finalized_quote_receipt(context, self.iid, key, encoded(self.value if value is None else value))

    def counts(self):
        return tuple(self.store._live.connection.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in ("ruby_finalized_quote_events", "ruby_finalized_quote_receipts", "ruby_finalized_quote_audit"))

    def test_quote_restart_original_receipt_encryption_no_authority(self):
        self.setup_quote(); result = self.record()
        self.assertEqual(self.counts(), (1,1,1))
        self.assertEqual(self.record(), result)
        self.assertEqual(self.resolve_quote(), result)
        detail = self.store.get_ruby_finalized_quote(CONTEXT, self.iid, result["quote_id"])
        self.assertEqual(detail["quote"], self.value)
        for name, value in NO_QUOTE_AUTHORITY.items():
            self.assertEqual(result[name], value)
        encrypted = self.config.state_file.read_bytes()
        self.assertNotIn(b"Synthetic custom cake", encrypted)
        self.assertNotIn(QUOTE_KEY.encode(), encrypted)
        self.assertNotIn(b"example.invalid", encrypted)
        self.store.close(); self.store = self.open()
        self.assertEqual(self.resolve_quote(), result)
        self.assertEqual(self.store.get_ruby_finalized_quote(CONTEXT, self.iid, result["quote_id"]), detail)

    def test_quote_child_process_restart(self):
        self.setup_quote(); result=self.record(); self.store.close()
        script='''
import json,sys
from pathlib import Path
from dataclasses import replace
from conversation_store import ConversationStore,ConversationConfig
from test_ruby_inquiry import POLICY,CONTEXT,ISSUER,SUBJECT,encoded
from test_ruby_finalized_quote import QUOTE_KEY,quote
root=Path(sys.argv[1]);s=ConversationStore(ConversationConfig(root/'state.enc',root/'ledger.enc',root/'synthetic.key'),ISSUER,SUBJECT,ruby_inquiry_policy=lambda c:replace(POLICY,finalized_quotes_enabled=True),ruby_finalized_quotes_enabled=True)
print(json.dumps(s.resolve_ruby_finalized_quote_receipt(CONTEXT,sys.argv[2],QUOTE_KEY,encoded(quote(sys.argv[3])))))
s.close()
'''
        completed=subprocess.run([sys.executable,'-c',script,str(self.root),self.iid,self.value['expected_revision_id']],cwd=Path(__file__).parent,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(completed.stdout),result);self.store=self.open()

    def test_quote_changed_key_conflict_stale_first_append_replay_after_revision_catalog(self):
        self.setup_quote(); result=self.record()
        changed=copy.deepcopy(self.value); changed['items'][0]['description']='Changed'
        with self.assertRaisesRegex(ConversationRequestError,'idempotency_conflict'): self.record(changed)
        revised=body(); revised['customization']['custom_notes']='Later inquiry'
        self.store.revise_ruby_inquiry(CONTEXT,self.iid,'synthetic-revise-key-0002',encoded({'expected_revision_id':self.value['expected_revision_id'],'inquiry':revised}))
        self.policy=replace(POLICY,catalog_revision='later-catalog',catalog_prices=(("CAKE-A",9000),))
        self.assertEqual(self.record(),result);self.assertEqual(self.resolve_quote(),result)
        with self.assertRaisesRegex(ConversationRequestError,'stale_revision'): self.record(key='synthetic-new-quote-key-0002')
        self.assertEqual(self.counts(),(1,1,1))

    def test_quote_missing_each_evidence_unknown_no_replacement(self):
        for table in ('ruby_finalized_quote_events','ruby_finalized_quote_receipts','ruby_finalized_quote_audit'):
            with self.subTest(table=table):
                self.setup_quote();result=self.record()
                self.store._live.connection.execute('DELETE FROM '+table+' WHERE quote_id=?',(result['quote_id'],))
                before=self.counts()
                self.assertEqual(self.resolve_quote()['state'],'unknown')
                self.assertEqual(self.record()['state'],'unknown')
                self.assertEqual(self.counts(),before)
                # Dispose corrupted synthetic store before the next independent case.
                self.store.close();self.temp.cleanup();self.setUp()

    def test_quote_absent_history_resolution_never_writes(self):
        self.setup_quote();before=self.counts()
        self.assertEqual(self.resolve_quote()['state'],'unknown')
        self.assertEqual(self.counts(),before)

    def test_quote_atomic_failures_all_three_rows_roll_back(self):
        self.setup_quote()
        for stage in ('event','receipt','audit'):
            def fail(current):
                if current==stage: raise RuntimeError('synthetic failure')
            with patch.object(self.store,'_quote_stage',fail):
                with self.assertRaisesRegex(ConversationRequestError,'quote_write_failed'):self.record()
            self.assertEqual(self.counts(),(0,0,0))
        self.record();self.assertEqual(self.counts(),(1,1,1))

    def test_quote_post_replace_uncertainty_fences_all_until_reconcile(self):
        self.setup_quote();persist=self.store._live.persist
        def failed():
            persist();raise OSError('synthetic post replace')
        with patch.object(self.store._live,'persist',failed):
            with self.assertRaisesRegex(ConversationRequestError,'quote_outcome_unknown'): self.record()
        with self.assertRaisesRegex(ConversationRequestError,'conversation_store_fenced'): self.resolve_quote()
        with self.assertRaisesRegex(ConversationRequestError,'conversation_store_fenced'): self.store.get_ruby_inquiry(CONTEXT,self.iid)
        self.store.reconcile_persistence(ISSUER,SUBJECT,inquiry_context=CONTEXT)
        result=self.resolve_quote();self.assertEqual(result['state'],'owner_quote_recorded')
        self.assertEqual(self.record(),result);self.assertEqual(self.counts(),(1,1,1))

    def test_quote_pre_replace_uncertainty_resolves_unknown_no_automatic_retry(self):
        self.setup_quote()
        with patch.object(self.store._live,'persist',side_effect=OSError('synthetic pre replace')):
            with self.assertRaisesRegex(ConversationRequestError,'quote_outcome_unknown'): self.record()
        self.store.reconcile_persistence(ISSUER,SUBJECT,inquiry_context=CONTEXT)
        self.assertEqual(self.resolve_quote()['state'],'unknown');self.assertEqual(self.counts(),(0,0,0))

    def test_quote_current_owner_project_source_and_policy(self):
        self.setup_quote();result=self.record()
        for context in (replace(CONTEXT,subject='another-owner'),replace(CONTEXT,project_id='other-project'),replace(CONTEXT,source_instance='other-instance'),replace(CONTEXT,source_system='other-source')):
            for action in (lambda:self.record(context=context),lambda:self.resolve_quote(context=context),lambda:self.store.get_ruby_finalized_quote(context,self.iid,result['quote_id'])):
                with self.assertRaises(ConversationRequestError):action()
        self.policy=None
        for action in (self.record,self.resolve_quote,lambda:self.store.get_ruby_finalized_quote(CONTEXT,self.iid,result['quote_id'])):
            with self.assertRaisesRegex(ConversationRequestError,'inquiry_policy_unavailable'):action()
        self.policy=replace(POLICY,synthetic_only=False)
        with self.assertRaisesRegex(ConversationRequestError,'inquiry_policy_unavailable'):self.record()

    def test_quote_default_off_policy_opt_in_and_retained_custody_guard(self):
        self.setup_quote();self.store._ruby_finalized_quotes_enabled=False
        with self.assertRaisesRegex(ConversationRequestError,'quote_policy_unavailable'):self.record()
        self.store._ruby_finalized_quotes_enabled=True
        self.store._ruby_inquiry_policy=lambda c:POLICY
        with self.assertRaisesRegex(ConversationRequestError,'quote_policy_unavailable'):self.record()
        self.store._ruby_inquiry_policy=lambda c:replace(POLICY,finalized_quotes_enabled=True)
        self.record();self.store.close()
        with self.assertRaisesRegex(ConversationConfigurationError,'quote_opt_in_required_for_custody'):
            ConversationStore(self.config,ISSUER,SUBJECT,ruby_inquiry_policy=lambda c:POLICY)
        self.store=self.open()

    def test_quote_closed_validation_rejects_authority_and_bad_money(self):
        self.setup_quote()
        changes=[('customer_accepted',True),('customer_ref','caller-chosen'),('total_yen',True),('total_yen',6201),('shipping_yen',-1),('currency','USD')]
        for key,value in changes:
            changed=copy.deepcopy(self.value);changed[key]=value
            with self.assertRaises(ConversationRequestError):self.record(changed)
        changed=copy.deepcopy(self.value);changed['items'][0]['quantity']=True
        with self.assertRaises(ConversationRequestError):self.record(changed)
        changed=copy.deepcopy(self.value);changed['fulfillment']['date']='2028-02-30'
        with self.assertRaises(ConversationRequestError):self.record(changed)
        self.assertEqual(self.counts(),(0,0,0))

    def test_quote_concurrent_same_key_single_event(self):
        from concurrent.futures import ThreadPoolExecutor
        self.setup_quote()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:self.record(),range(16)))
        self.assertTrue(all(r==results[0] for r in results));self.assertEqual(self.counts(),(1,1,1))

    def test_quote_policy_revocation_blocks_reconciliation(self):
        self.setup_quote()
        with patch.object(self.store._live,'persist',side_effect=OSError('synthetic failure')):
            with self.assertRaises(ConversationRequestError):self.record()
        self.policy=None
        with self.assertRaisesRegex(ConversationRequestError,'inquiry_policy_unavailable'):
            self.store.reconcile_persistence(ISSUER,SUBJECT,inquiry_context=CONTEXT)
        self.assertTrue(self.store._persistence_fenced)

    def test_quote_customer_reference_is_scoped_not_identity(self):
        self.setup_quote();one=self.record()
        next_inquiry=self.create(key='synthetic-second-inquiry-002')
        iid=next_inquiry['receipt']['inquiry_id'];value=quote(next_inquiry['receipt']['revision_id'])
        two=self.store.record_ruby_finalized_quote(CONTEXT,iid,QUOTE_KEY,encoded(value))
        self.assertNotEqual(one['customer_ref'],two['customer_ref'])
        self.assertEqual(one['customer_identity'],'declared_synthetic_unverified')

    def test_quote_audit_identifier_only_no_content(self):
        self.setup_quote();self.record()
        audit=dict(self.store._live.connection.execute('SELECT * FROM ruby_finalized_quote_audit').fetchone())
        self.assertNotIn('request_json',audit);self.assertNotIn('response_json',audit)
        self.assertNotIn('customer_ref',audit)
        self.assertNotIn('Synthetic custom cake',repr(audit))
        self.assertNotIn('example.invalid',repr(audit));self.assertNotIn(QUOTE_KEY,repr(audit))

    def test_quote_readonly_preflight_no_writes(self):
        self.setup_quote();self.record();self.store.close()
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        with patch.dict(os.environ,{'MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT':'true'}):
            store=self.open()
            try:
                with self.assertRaisesRegex(ConversationRequestError,'inquiry_readonly'):
                    store.resolve_ruby_finalized_quote_receipt(CONTEXT,self.iid,QUOTE_KEY,encoded(self.value))
            finally:store.close()
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})
        self.store=self.open()

    def test_quote_receipt_tamper_rejects_no_reconstruction(self):
        self.setup_quote();result=self.record()
        changed=dict(result,customer_accepted=True)
        self.store._live.connection.execute('UPDATE ruby_finalized_quote_receipts SET response_json=?',(json.dumps(changed),))
        with self.assertRaisesRegex(ConversationRequestError,'quote_binding_mismatch'):self.resolve_quote()
        self.assertEqual(self.counts(),(1,1,1))


if __name__=='__main__': unittest.main()

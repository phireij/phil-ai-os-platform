"""Disposable synthetic state-machine checks. No network or real identity."""
import copy
import json
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from conversation_store import ConversationStore, ConversationRequestError, ConversationConfigurationError
from test_ruby_inquiry import InquiryChecks, ISSUER, SUBJECT, CONTEXT, POLICY, body, encoded
from test_ruby_finalized_quote import quote, QUOTE_KEY
from ruby_finalized_quote import NO_QUOTE_AUTHORITY
from ruby_quote_custody import SyntheticResponseVerification, SCHEMA, fingerprint, CUSTODY_TABLES

SELECT_KEY = "synthetic-select-key-0001"
RESPONSE_KEY = "synthetic-response-key-0001"
CONSENT = "SYNTHETIC CONSENT ONLY. No customer, order, payment, or fulfillment authority."


def verifier(context, inquiry_id, quote_id, customer_ref, request_fingerprint):
    return SyntheticResponseVerification(inquiry_id, quote_id, customer_ref, request_fingerprint, "synthetic:customer-one")


class CustodyChecks(unittest.TestCase):
    setUp = InquiryChecks.setUp
    tearDown = InquiryChecks.tearDown
    create = InquiryChecks.create

    def open(self):
        return ConversationStore(self.config, ISSUER, SUBJECT,
            ruby_inquiry_policy=lambda c: replace(self.policy, finalized_quotes_enabled=True, quote_custody_enabled=True) if self.policy else None,
            ruby_finalized_quotes_enabled=True, ruby_quote_custody_enabled=True,
            ruby_quote_synthetic_verifier=verifier)

    def setup_offer(self):
        inquiry = self.create()["receipt"]
        self.iid = inquiry["inquiry_id"]
        self.quote_body = quote(inquiry["revision_id"])
        self.quote_receipt = self.store.record_ruby_finalized_quote(CONTEXT, self.iid, QUOTE_KEY, encoded(self.quote_body))
        self.selection = {"schema_version": SCHEMA, "operation": "select", "expected_event_id": None,
            "quote_id": self.quote_receipt["quote_id"], "quote_fingerprint": self.quote_receipt["request_fingerprint"], "consent_text": CONSENT}
        self.selected = self.record(self.selection, SELECT_KEY)
        self.response = {"schema_version": SCHEMA, "operation": "respond", "expected_event_id": self.selected["event_id"],
            "quote_id": self.quote_receipt["quote_id"], "quote_fingerprint": self.quote_receipt["request_fingerprint"],
            "consent_fingerprint": fingerprint(CONSENT.encode()), "decision": "accept"}

    def record(self, value=None, key=RESPONSE_KEY, context=CONTEXT):
        return self.store.record_ruby_quote_custody(context, self.iid, key, encoded(self.response if value is None else value))

    def resolve(self, value=None, key=RESPONSE_KEY, context=CONTEXT):
        return self.store.resolve_ruby_quote_custody_receipt(context, self.iid, key, encoded(self.response if value is None else value))

    def view(self):
        return self.store.get_ruby_quote_custody(CONTEXT, self.iid)

    def counts(self):
        return tuple(self.store._live.connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] for table in CUSTODY_TABLES)

    def withdrawal(self, head):
        return {"schema_version": SCHEMA, "operation": "withdraw", "expected_event_id": head, "quote_id": self.quote_receipt["quote_id"]}

    def next_quote(self, head):
        value = copy.deepcopy(self.quote_body)
        value["items"][0].update(quantity=1, unit_price_yen=300, line_total_yen=300)
        value.update(shipping_yen=0, total_yen=300)
        result = self.store.record_ruby_finalized_quote(CONTEXT, self.iid, "synthetic-price-revision-002", encoded(value))
        selected = dict(self.selection, expected_event_id=head, quote_id=result["quote_id"], quote_fingerprint=result["request_fingerprint"])
        return result, selected

    def test_roundtrip_restart_encrypted_original_no_authority(self):
        self.setup_offer(); result = self.record()
        self.assertEqual(self.counts(), (2, 2, 2, 1))
        self.assertEqual(self.record(), result); self.assertEqual(self.resolve(), result)
        current = self.view(); self.assertEqual(current["synthetic_decision"], "accept")
        for output in (result, self.selected, current):
            for name, value in NO_QUOTE_AUTHORITY.items(): self.assertEqual(output[name], value)
            self.assertIs(output["customer_identity_verified"], False)
            self.assertIs(output["current_quote_verified"], False)
        raw = self.config.state_file.read_bytes()
        for marker in (CONSENT, "synthetic:customer-one", RESPONSE_KEY): self.assertNotIn(marker.encode(), raw)
        self.store.close(); self.store = self.open()
        self.assertEqual(self.resolve(), result); self.assertEqual(self.view(), current)

    def test_real_child_restart(self):
        self.setup_offer(); result = self.record(); self.store.close()
        script = '''
import json,sys
from pathlib import Path
from dataclasses import replace
from conversation_store import ConversationConfig,ConversationStore
from test_ruby_inquiry import ISSUER,SUBJECT,POLICY,CONTEXT,encoded
from test_ruby_quote_custody import verifier,RESPONSE_KEY
p=Path(sys.argv[1]);s=ConversationStore(ConversationConfig(p/'state.enc',p/'ledger.enc',p/'synthetic.key'),ISSUER,SUBJECT,ruby_inquiry_policy=lambda c:replace(POLICY,finalized_quotes_enabled=True,quote_custody_enabled=True),ruby_finalized_quotes_enabled=True,ruby_quote_custody_enabled=True,ruby_quote_synthetic_verifier=verifier)
print(json.dumps(s.resolve_ruby_quote_custody_receipt(CONTEXT,sys.argv[2],RESPONSE_KEY,encoded(json.loads(sys.argv[3])))))
s.close()
'''
        run = subprocess.run([sys.executable, "-c", script, str(self.root), self.iid, json.dumps(self.response)], cwd=Path(__file__).parent, text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(run.stdout), result); self.store = self.open()

    def test_same_inquiry_new_price_requires_new_response(self):
        self.setup_offer(); old = self.record()
        new_quote, selection = self.next_quote(old["event_id"])
        self.record(selection, "synthetic-select-key-0002")
        self.assertEqual(self.view()["quote_id"], new_quote["quote_id"])
        self.assertIsNone(self.view()["synthetic_decision"])
        self.assertEqual(self.resolve(), old); self.assertEqual(self.record(), old)
        with self.assertRaisesRegex(ConversationRequestError, "stale_quote_custody"):
            self.record(key="synthetic-stale-response-02")
        self.assertEqual(self.view()["quote_id"], new_quote["quote_id"])

    def test_recording_content_does_not_silently_publish_offer(self):
        self.setup_offer(); self.next_quote(self.selected["event_id"])
        self.assertEqual(self.view()["quote_id"], self.quote_receipt["quote_id"])

    def test_withdrawal_preserves_history_invalidates_currentness(self):
        self.setup_offer(); result = self.record()
        withdrawn = self.record(self.withdrawal(result["event_id"]), "synthetic-withdraw-key-001")
        self.assertEqual(self.view()["state"], "withdrawn")
        self.assertEqual(self.resolve(), result); self.assertEqual(self.record(), result)
        with self.assertRaisesRegex(ConversationRequestError, "quote_not_current"):
            self.record(dict(self.response, expected_event_id=withdrawn["event_id"]), "synthetic-new-response-02")
        with self.assertRaisesRegex(ConversationRequestError, "quote_already_selected"):
            self.record(dict(self.selection, expected_event_id=withdrawn["event_id"]), "synthetic-reselect-key-02")

    def test_decline_and_conflicting_decision_are_not_acceptance(self):
        self.setup_offer(); result = self.record(dict(self.response, decision="decline"))
        self.assertEqual(self.view()["synthetic_decision"], "decline")
        self.assertIs(self.view()["customer_accepted"], False)
        with self.assertRaisesRegex(ConversationRequestError, "idempotency_conflict"): self.record()
        with self.assertRaisesRegex(ConversationRequestError, "quote_already_responded"):
            self.record(dict(self.response, expected_event_id=result["event_id"]), "synthetic-conflict-key-002")

    def test_inquiry_revision_makes_offer_stale(self):
        self.setup_offer(); revised = body(); revised["customization"]["custom_notes"] = "Changed synthetic inquiry"
        self.store.revise_ruby_inquiry(CONTEXT, self.iid, "synthetic-inquiry-revise-02", encoded({"expected_revision_id": self.quote_body["expected_revision_id"], "inquiry": revised}))
        self.assertEqual(self.view()["state"], "stale_inquiry_revision")
        with self.assertRaisesRegex(ConversationRequestError, "stale_revision"): self.record()

    def test_verifier_is_test_only_exact_quote_customer_and_request(self):
        self.setup_offer(); before = self.counts()
        changes = [dict(inquiry_id="another-inquiry-00000"), dict(quote_id="another-quote-000000"),
                   dict(customer_ref="wrong-customer"), dict(request_fingerprint="sha256:"+"0"*64),
                   dict(actor_ref="real-customer"), dict(synthetic_only=False), dict(synthetic_only=1)]
        for change in changes:
            with self.subTest(change=change):
                def wrong(*args): return replace(verifier(*args), **change)
                self.store._ruby_quote_synthetic_verifier = wrong
                with self.assertRaisesRegex(ConversationRequestError, "synthetic_verification_rejected"): self.record()
        self.store._ruby_quote_synthetic_verifier = lambda *a: {"verified": True}
        with self.assertRaisesRegex(ConversationRequestError, "synthetic_verification_rejected"): self.record()
        self.store._ruby_quote_synthetic_verifier = lambda *a: 1/0
        with self.assertRaisesRegex(ConversationRequestError, "synthetic_verification_unavailable"): self.record()
        self.assertEqual(self.counts(), before)

    def test_idempotency_cannot_change_actor(self):
        self.setup_offer(); self.record()
        self.store._ruby_quote_synthetic_verifier = lambda *a: replace(verifier(*a), actor_ref="synthetic:other")
        with self.assertRaisesRegex(ConversationRequestError, "idempotency_conflict"): self.record()

    def test_consent_and_quote_hash_and_closed_authority_input(self):
        self.setup_offer(); before = self.counts()
        for field, val in (("quote_fingerprint", "sha256:"+"0"*64), ("consent_fingerprint", "sha256:"+"1"*64),
                           ("customer_accepted", True), ("actor_ref", "synthetic:customer-one"), ("decision", True)):
            with self.subTest(field=field):
                with self.assertRaises(ConversationRequestError): self.record(dict(self.response, **{field:val}))
        self.assertEqual(self.counts(), before)

    def test_all_transaction_failure_stages_roll_back(self):
        self.setup_offer(); before = self.counts(); view = self.view()
        for failed_stage in ("event", "receipt", "audit", "head"):
            def fail(stage):
                if stage == failed_stage: raise OSError("synthetic staged failure")
            with patch.object(self.store, "_custody_stage", fail):
                with self.assertRaisesRegex(ConversationRequestError, "quote_custody_write_failed"): self.record()
            self.assertEqual(self.counts(), before); self.assertEqual(self.view(), view)
        self.record()

    def test_post_replace_unknown_fences_and_recovers_original(self):
        self.setup_offer(); persist = self.store._live.persist
        def failed(): persist(); raise OSError("synthetic after replace")
        with patch.object(self.store._live, "persist", failed):
            with self.assertRaisesRegex(ConversationRequestError, "quote_custody_outcome_unknown"): self.record()
        for action in (self.record, self.resolve, self.view):
            with self.assertRaisesRegex(ConversationRequestError, "conversation_store_fenced"): action()
        self.store.reconcile_persistence(ISSUER, SUBJECT, inquiry_context=CONTEXT)
        result = self.resolve(); self.assertEqual(self.record(), result)
        self.assertEqual(self.counts(), (2,2,2,1)); self.assertEqual(self.view()["synthetic_decision"], "accept")

    def test_pre_replace_unknown_is_not_retry_permission(self):
        self.setup_offer(); before = self.counts()
        with patch.object(self.store._live, "persist", side_effect=OSError("synthetic before replace")):
            with self.assertRaisesRegex(ConversationRequestError, "quote_custody_outcome_unknown"): self.record()
        self.store.reconcile_persistence(ISSUER, SUBJECT, inquiry_context=CONTEXT)
        self.assertEqual(self.resolve()["state"], "unknown")
        self.assertEqual(self.counts(), before); self.assertIsNone(self.view()["synthetic_decision"])

    def test_partial_history_or_orphan_receipt_never_reconstructed(self):
        for table in CUSTODY_TABLES:
            with self.subTest(table=table):
                self.setup_offer(); self.record()
                self.store._live.connection.execute("DELETE FROM " + table)
                before = self.counts()
                self.assertEqual(self.resolve()["state"], "unknown")
                self.assertEqual(self.record()["state"], "unknown")
                self.assertEqual(self.view()["state"], "unknown")
                self.assertEqual(self.counts(), before)
                self.store.close(); self.temp.cleanup(); self.setUp()
        self.setup_offer(); self.record()
        for table in CUSTODY_TABLES:
            if table != "ruby_quote_custody_receipts": self.store._live.connection.execute("DELETE FROM " + table)
        self.assertEqual(self.record()["state"], "unknown")

    def test_source_quote_history_missing_cannot_resolve_response(self):
        self.setup_offer(); self.record()
        self.store._live.connection.execute("DELETE FROM ruby_finalized_quote_receipts")
        self.assertEqual(self.resolve()["state"], "unknown")
        self.assertEqual(self.view()["state"], "unknown")

    def test_current_quote_dependency_scope_and_historical_recovery(self):
        self.setup_offer(); old = self.record()
        next_quote, selection = self.next_quote(old["event_id"])
        self.record(selection, "synthetic-select-key-0002")
        self.store._live.connection.execute("DELETE FROM ruby_finalized_quote_audit WHERE quote_id=?", (self.quote_receipt["quote_id"],))
        self.assertEqual(self.resolve()["state"], "unknown")
        self.assertEqual(self.view()["quote_id"], next_quote["quote_id"])
        self.assertEqual(self.view()["state"], "synthetic_current_offer")

    def test_readonly_receipt_recovery_does_not_invoke_fixture_verifier(self):
        self.setup_offer(); result = self.record()
        def unavailable(*args): raise RuntimeError("synthetic verifier removed")
        self.store._ruby_quote_synthetic_verifier = unavailable
        with self.assertRaisesRegex(ConversationRequestError, "synthetic_verification_unavailable"): self.record()
        self.assertEqual(self.resolve(), result)

    def test_changed_key_content_conflicts_before_missing_quote_resolution(self):
        self.setup_offer(); self.record()
        with self.assertRaisesRegex(ConversationRequestError, "idempotency_conflict"):
            self.record(dict(self.response, quote_id="missing-quote-0000000"))

    def test_process_exit_before_and_after_custody_snapshot(self):
        script = '''
import json,sys,os
from pathlib import Path
from dataclasses import replace
import conversation_store as core
from conversation_store import ConversationConfig,ConversationStore
from test_ruby_inquiry import ISSUER,SUBJECT,POLICY,CONTEXT,encoded
from test_ruby_quote_custody import verifier,RESPONSE_KEY
p=Path(sys.argv[1]);s=ConversationStore(ConversationConfig(p/'state.enc',p/'ledger.enc',p/'synthetic.key'),ISSUER,SUBJECT,ruby_inquiry_policy=lambda c:replace(POLICY,finalized_quotes_enabled=True,quote_custody_enabled=True),ruby_finalized_quotes_enabled=True,ruby_quote_custody_enabled=True,ruby_quote_synthetic_verifier=verifier)
original=core._atomic_write_private
def crash(path,data,**kwargs):
    if sys.argv[4]=='after': original(path,data,**kwargs)
    os._exit(23)
core._atomic_write_private=crash
s.record_ruby_quote_custody(CONTEXT,sys.argv[2],RESPONSE_KEY,encoded(json.loads(sys.argv[3])))
'''
        for mode in ("before", "after"):
            self.setup_offer(); self.store.close()
            run = subprocess.run([sys.executable, "-c", script, str(self.root), self.iid, json.dumps(self.response), mode], cwd=Path(__file__).parent, text=True, capture_output=True)
            self.assertEqual(run.returncode, 23, run.stderr)
            self.store = self.open()
            result = self.resolve()
            if mode == "before":
                self.assertEqual(result["state"], "unknown"); self.assertIsNone(self.view()["synthetic_decision"])
            else:
                self.assertEqual(result["state"], "synthetic_event_recorded"); self.assertEqual(self.record(), result)
            self.store.close(); self.temp.cleanup(); self.setUp()

    def test_receipt_tampering_not_regenerated(self):
        self.setup_offer(); result = self.record()
        changed = dict(result, customer_accepted=True)
        self.store._live.connection.execute("UPDATE ruby_quote_custody_receipts SET response_json=? WHERE event_id=?", (json.dumps(changed), result["event_id"]))
        for action in (self.record, self.resolve, self.view):
            with self.assertRaisesRegex(ConversationRequestError, "quote_custody_binding_mismatch"): action()

    def test_cross_scope_and_current_policy_revocation(self):
        self.setup_offer(); self.record()
        for field, val in (("subject", "other-owner"), ("project_id", "other-project"), ("source_system", "other-source"), ("source_instance", "other-instance")):
            context = replace(CONTEXT, **{field: val})
            for action in (lambda: self.record(context=context), lambda: self.resolve(context=context), lambda: self.store.get_ruby_quote_custody(context, self.iid)):
                with self.assertRaises(ConversationRequestError): action()
        self.policy = None
        for action in (self.record, self.resolve, self.view):
            with self.assertRaisesRegex(ConversationRequestError, "inquiry_policy_unavailable"): action()

    def test_cross_inquiry_quote_reference_unknown(self):
        self.setup_offer(); another = self.create(key="synthetic-other-inquiry-002")["receipt"]
        other = self.store.record_ruby_finalized_quote(CONTEXT, another["inquiry_id"], QUOTE_KEY, encoded(quote(another["revision_id"])))
        self.assertEqual(self.record(dict(self.response, quote_id=other["quote_id"]))["state"], "unknown")
        self.assertEqual(self.counts(), (1,1,1,1))

    def test_default_off_and_retained_custody_requires_opt_in(self):
        self.setup_offer(); self.record(); self.store._ruby_quote_custody_enabled = False
        with self.assertRaisesRegex(ConversationRequestError, "quote_custody_policy_unavailable"): self.resolve()
        self.store._ruby_quote_custody_enabled = True
        self.store._ruby_inquiry_policy = lambda c: replace(POLICY, finalized_quotes_enabled=True)
        with self.assertRaisesRegex(ConversationRequestError, "quote_custody_policy_unavailable"): self.resolve()
        self.store.close(); before = self.config.state_file.read_bytes()
        with self.assertRaisesRegex(ConversationConfigurationError, "quote_custody_opt_in_required"):
            ConversationStore(self.config, ISSUER, SUBJECT, ruby_inquiry_policy=lambda c: replace(POLICY, finalized_quotes_enabled=True), ruby_finalized_quotes_enabled=True)
        self.assertEqual(self.config.state_file.read_bytes(), before)
        self.store = self.open()

    def test_configuration_requires_synthetic_verifier_and_quote_custody(self):
        self.store.close()
        for kwargs in ({"ruby_quote_custody_enabled": True}, {"ruby_quote_synthetic_verifier": verifier}, {"ruby_quote_custody_enabled": 1}):
            with self.assertRaisesRegex(ConversationConfigurationError, "quote_custody_synthetic_mode_required"):
                ConversationStore(self.config, ISSUER, SUBJECT, **kwargs)
        self.store = self.open()

    def test_concurrent_duplicate_and_competing_decisions(self):
        self.setup_offer()
        with ThreadPoolExecutor(max_workers=8) as pool: results = list(pool.map(lambda _: self.record(), range(16)))
        self.assertTrue(all(x == results[0] for x in results)); self.assertEqual(self.counts(), (2,2,2,1))
        self.store.close(); self.temp.cleanup(); self.setUp(); self.setup_offer()
        def compete(decision):
            try: return self.record(dict(self.response, decision=decision), "synthetic-race-"+decision)
            except ConversationRequestError as exc: return str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(compete, ("accept", "decline")))
        self.assertEqual(sum(type(x) is dict for x in results), 1)
        self.assertEqual(self.counts(), (2,2,2,1))

    def test_racing_withdrawal_and_response_linearize(self):
        self.setup_offer()
        def run(value, key):
            try: return self.record(value, key)
            except ConversationRequestError as exc: return str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, self.response, RESPONSE_KEY), pool.submit(run, self.withdrawal(self.selected["event_id"]), "synthetic-race-withdraw")]
            results = [f.result() for f in futures]
        self.assertEqual(sum(type(x) is dict for x in results), 1)
        self.assertEqual(self.counts(), (2,2,2,1))

    def test_audit_is_identifier_only(self):
        self.setup_offer(); self.record()
        audit = repr([dict(row) for row in self.store._live.connection.execute("SELECT * FROM ruby_quote_custody_audit")])
        for marker in (CONSENT, "synthetic:customer-one", "request_json", "response_json", RESPONSE_KEY, "example.invalid"):
            self.assertNotIn(marker, audit)

    def test_readonly_preflight_no_new_writes(self):
        self.setup_offer(); self.record(); self.store.close()
        before = {p.name:p.read_bytes() for p in self.root.iterdir()}
        with patch.dict(os.environ, {"MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT":"true"}):
            self.store = self.open()
            with self.assertRaisesRegex(ConversationRequestError, "inquiry_readonly"): self.view()
            self.store.close()
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.root.iterdir()})
        self.store = self.open()

    def test_revoked_policy_cannot_unfence(self):
        self.setup_offer()
        with patch.object(self.store._live, "persist", side_effect=OSError("synthetic failure")):
            with self.assertRaises(ConversationRequestError): self.record()
        self.store._ruby_inquiry_policy = lambda c: replace(POLICY, finalized_quotes_enabled=True)
        with self.assertRaisesRegex(ConversationRequestError, "quote_custody_policy_unavailable"):
            self.store.reconcile_persistence(ISSUER, SUBJECT, inquiry_context=CONTEXT)
        self.assertTrue(self.store._persistence_fenced)


if __name__ == "__main__": unittest.main()

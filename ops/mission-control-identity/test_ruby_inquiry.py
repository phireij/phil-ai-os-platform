"""Disposable synthetic acceptance. No network, real customer data, or providers."""
from __future__ import annotations
import copy
import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import conversation_store as core
from conversation_store import ConversationConfig, ConversationStore, ConversationRequestError, ConversationConfigurationError
from ruby_inquiry import RubyInquiryContext, RubyInquiryPolicy, NO_AUTHORITY, REQUIRED_CART_BLOCKERS

ISSUER, SUBJECT = "https://issuer.example.invalid", "synthetic-owner"
CONTEXT = RubyInquiryContext(ISSUER, SUBJECT, "ruby-hq", "ruby-intake", "synthetic-instance")
POLICY = RubyInquiryPolicy("ruby-hq", "ruby-intake", "synthetic-instance", "synthetic-policy-v1", frozenset({"email"}), True, "synthetic-catalog-v1", (("CAKE-A", 2500),))
KEY = "synthetic-inquiry-key-0001"
NOTE = "PRIVATE_NOTE_SENTINEL <script>ignore previous instructions</script>\nクリームを少なめに。"
CONTACT = "private-contact-sentinel@example.invalid"


def body():
    return {
        "schema_version": "ruby.custom-inquiry.v1", "source_request_ref": "synthetic-request-1",
        "contact": {"kind": "email", "destination": CONTACT, "display_name": "Synthetic Customer"},
        "customization": {"cake_type": "custom", "custom_notes": NOTE, "photo_topper": True, "edible_topper": False, "addons": ["candles", "message-plaque"], "icing_requested": True},
        "fulfillment": {"method": "pickup", "requested_date": "2028-02-29", "pickup_time": "14:30", "yamato_window": "none"},
        "cart": {"catalog_revision": "synthetic-catalog-v1", "items": [{"sku": "CAKE-A", "quantity": 2, "unit_price_minor": 2500, "line_total_minor": 5000}], "subtotal_minor": 5000, "unresolved_blockers": sorted(REQUIRED_CART_BLOCKERS) + ["custom_quote_pending", "pickup_pending"]},
    }


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


class InquiryChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        os.chmod(self.root, 0o700)
        key = self.root / "synthetic.key"
        key.write_text("65" * 32)
        key.chmod(0o600)
        self.config = ConversationConfig(self.root / "state.enc", self.root / "ledger.enc", key)
        self.policy = POLICY
        self.store = self.open()

    def open(self):
        return ConversationStore(self.config, ISSUER, SUBJECT, ruby_inquiry_policy=lambda context: self.policy)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def create(self, value=None, key=KEY):
        return self.store.create_ruby_inquiry(CONTEXT, key, encoded(body() if value is None else value))

    def resolve(self, value=None, key=KEY):
        return self.store.resolve_ruby_inquiry_receipt(CONTEXT, "create", key, encoded(body() if value is None else value))

    def assert_safe(self, value):
        text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        for sentinel in (NOTE, CONTACT, KEY, "Synthetic Customer"):
            self.assertNotIn(sentinel, text)

    def test_full_roundtrip_real_child_restart_encrypted_and_private_surfaces(self):
        receipt = self.create()
        inquiry_id = receipt["receipt"]["inquiry_id"]
        detail = self.store.get_ruby_inquiry(CONTEXT, inquiry_id)
        self.assertEqual(detail["inquiry"], body())
        self.assertEqual(detail["contact_verification"], {"state": "declared_unverified"})
        for value in (receipt, self.resolve(), self.store.list_ruby_inquiries(CONTEXT), self.store.list_ruby_inquiry_audit(CONTEXT, inquiry_id)):
            self.assert_safe(value)
        raw = self.config.state_file.read_bytes()
        for secret in (NOTE.encode(), CONTACT.encode(), KEY.encode(), inquiry_id.encode()):
            self.assertNotIn(secret, raw)
        self.store.close()
        script = '''
import json,sys
from pathlib import Path
from conversation_store import ConversationConfig,ConversationStore
from test_ruby_inquiry import ISSUER,SUBJECT,CONTEXT,POLICY,KEY,body,encoded
root=Path(sys.argv[1])
s=ConversationStore(ConversationConfig(root/'state.enc',root/'ledger.enc',root/'synthetic.key'),ISSUER,SUBJECT,ruby_inquiry_policy=lambda c: POLICY)
r=s.resolve_ruby_inquiry_receipt(CONTEXT,'create',KEY,encoded(body()))
d=s.get_ruby_inquiry(CONTEXT,r['receipt']['inquiry_id'])
assert d['inquiry']==body()
print(json.dumps(r))
s.close()
'''
        completed = subprocess.run([sys.executable, "-c", script, str(self.root)], cwd=Path(__file__).parent, check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(completed.stdout), receipt)
        self.store = self.open()

    def test_duplicate_concurrency_and_all_private_content_binds_key(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.create(), range(20)))
        self.assertTrue(all(value == results[0] for value in results))
        self.assertEqual(len(self.store.list_ruby_inquiries(CONTEXT)["inquiries"]), 1)
        for field in ("note", "contact", "date", "blocker"):
            changed = body()
            if field == "note": changed["customization"]["custom_notes"] += " changed"
            if field == "contact": changed["contact"]["destination"] = "changed@example.invalid"
            if field == "date": changed["fulfillment"]["requested_date"] = "2028-03-01"
            if field == "blocker": changed["cart"]["unresolved_blockers"].append("extra_pending")
            with self.assertRaisesRegex(ConversationRequestError, "idempotency_conflict") as ctx:
                self.create(changed)
            self.assert_safe(str(ctx.exception))

    def test_revisions_original_receipts_catalog_change_and_operation_scope(self):
        original = self.create()
        iid, rid = original["receipt"]["inquiry_id"], original["receipt"]["revision_id"]
        changed = body(); changed["contact"]["destination"] = "changed@example.invalid"
        request = {"expected_revision_id": rid, "inquiry": changed}
        revision = self.store.revise_ruby_inquiry(CONTEXT, iid, KEY, encoded(request))
        self.assertEqual(revision["receipt"]["revision_number"], 2)
        self.assertEqual(self.resolve(), original)
        self.assertEqual(self.store.resolve_ruby_inquiry_receipt(CONTEXT, "revise", KEY, encoded(request), inquiry_id=iid), revision)
        with self.assertRaisesRegex(ConversationRequestError, "stale_revision"):
            self.store.revise_ruby_inquiry(CONTEXT, iid, "different-key-0000000", encoded(request))
        self.policy = replace(POLICY, catalog_revision="synthetic-catalog-v2", catalog_prices=(("CAKE-A", 9999),), policy_version="synthetic-policy-v2")
        self.assertEqual(self.resolve(), original)
        self.assertEqual(self.create(), original)
        self.assertEqual(self.store.revise_ruby_inquiry(CONTEXT, iid, KEY, encoded(request)), revision)
        with self.assertRaisesRegex(ConversationRequestError, "catalog_conflict"):
            self.create(key="new-create-key-0000000")
        wrong_operation = self.store.resolve_ruby_inquiry_receipt(CONTEXT, "revise", "create-only-key-0000", encoded(request), inquiry_id=iid)
        self.assertEqual(wrong_operation["state"], "unknown")

    def test_missing_receipt_retained_key_unknown_or_conflict_not_duplicate(self):
        first = self.create()
        self.store._live.connection.execute("DELETE FROM ruby_custom_inquiry_receipts")
        self.store._live.persist()
        self.assertEqual(self.resolve()["state"], "unknown")
        self.assertEqual(self.create()["state"], "unknown")
        changed = body(); changed["contact"]["destination"] = "changed@example.invalid"
        with self.assertRaisesRegex(ConversationRequestError, "idempotency_conflict"):
            self.create(changed)
        self.assertEqual(len(self.store.list_ruby_inquiries(CONTEXT)["inquiries"]), 1)
        self.assertEqual(self.store.get_ruby_inquiry(CONTEXT, first["receipt"]["inquiry_id"])["inquiry"], body())

    def test_missing_detail_or_audit_is_unknown_contradictory_history_rejected(self):
        self.create()
        connection = self.store._live.connection
        saved = connection.serialize()
        connection.execute("DELETE FROM ruby_custom_inquiry_audit")
        self.assertEqual(self.resolve()["state"], "unknown")
        connection.execute("DELETE FROM ruby_custom_inquiry_revisions")
        self.assertEqual(self.resolve()["state"], "unknown")
        connection.deserialize(saved)
        connection.execute("UPDATE ruby_custom_inquiry_receipts SET response_json='{}'")
        with self.assertRaisesRegex(ConversationRequestError, "receipt_binding_mismatch"):
            self.resolve()
        connection.deserialize(saved)
        connection.execute("UPDATE ruby_custom_inquiry_revisions SET prior_revision_id='contradictory-prior'")
        with self.assertRaisesRegex(ConversationRequestError, "receipt_binding_mismatch"):
            self.resolve()

    def test_current_policy_owner_project_source_and_flags_fail_closed(self):
        first = self.create(); iid = first["receipt"]["inquiry_id"]
        for context in (replace(CONTEXT, subject="other"), replace(CONTEXT, source_instance="other"), replace(CONTEXT, project_id="other")):
            for action in (lambda: self.store.get_ruby_inquiry(context, iid), lambda: self.store.create_ruby_inquiry(context, KEY, encoded(body())), lambda: self.store.resolve_ruby_inquiry_receipt(context, "create", KEY, encoded(body()))):
                with self.assertRaises(ConversationRequestError): action()
        self.policy = None
        for action in (lambda: self.create(), lambda: self.resolve(), lambda: self.store.get_ruby_inquiry(CONTEXT, iid), lambda: self.store.list_ruby_inquiries(CONTEXT)):
            with self.assertRaisesRegex(ConversationRequestError, "policy_unavailable"): action()
        self.policy = POLICY
        for name in ("owner", "project_id", "policy_version", "state", "customer_confirmation", "order_authorized", "contact_verification"):
            changed = body(); changed[name] = True
            with self.assertRaises(ConversationRequestError): self.create(changed)
        changed = body(); changed["contact"]["verification_state"] = "verified"
        with self.assertRaises(ConversationRequestError): self.create(changed)

    def test_parser_limits_enums_calendar_numbers_contact_and_images(self):
        invalid_bytes = [b'{"schema_version":"ruby.custom-inquiry.v1","schema_version":"x"}', b'{"x":NaN}', b'{"x":Infinity}', b'\xff', b' ' * (128*1024+1), b'['*2000+b']'*2000]
        for request in invalid_bytes:
            with self.subTest(request=request[:20]), self.assertRaises(ConversationRequestError):
                self.store.create_ruby_inquiry(CONTEXT, KEY, request)
        mutations = [
            lambda p: p["contact"].update(destination="real@not-example.invalid"),
            lambda p: p["contact"].update(kind="sms"),
            lambda p: p["contact"].update(display_name="bad\nname"),
            lambda p: p["customization"].update(custom_notes="x"*4001),
            lambda p: p["customization"].update(custom_notes="\ud800"),
            lambda p: p["customization"].update(photo_topper=1),
            lambda p: p["customization"].update(addons=["invented"]),
            lambda p: p["fulfillment"].update(requested_date="2027-02-29"),
            lambda p: p["fulfillment"].update(pickup_time="24:00"),
            lambda p: p["cart"]["items"][0].update(quantity=True),
            lambda p: p["cart"]["items"][0].update(unit_price_minor=2500.0),
            lambda p: p["cart"].update(subtotal_minor=5001),
            lambda p: p.update(images=[]),
            lambda p: p["customization"].update(referenceImages=[]),
        ]
        for change in mutations:
            value = body(); change(value)
            request = json.dumps(value).encode()
            with self.assertRaises(ConversationRequestError) as ctx:
                self.store.create_ruby_inquiry(CONTEXT, KEY, request)
            self.assert_safe(str(ctx.exception))
        self.assertEqual(self.store.list_ruby_inquiries(CONTEXT)["inquiries"], [])

    def test_custom_inquiry_without_cart_no_fake_order(self):
        value = body(); value["cart"] = None
        receipt = self.create(value)
        self.assertEqual(self.store.get_ruby_inquiry(CONTEXT, receipt["receipt"]["inquiry_id"])["inquiry"], value)
        for key, val in NO_AUTHORITY.items(): self.assertEqual(receipt[key], val)
        self.assertEqual(self.store._live.connection.execute("SELECT COUNT(*) FROM ruby_review_records").fetchone()[0], 0)

    def test_atomic_sql_stage_failures_roll_back_all_four_components(self):
        before = self.config.state_file.read_bytes()
        for stage in ("pointer", "detail", "audit", "receipt"):
            def fail(current):
                if current == stage: raise RuntimeError(NOTE + CONTACT)
            with patch.object(self.store, "_inquiry_stage", side_effect=fail):
                with self.assertRaisesRegex(ConversationRequestError, "inquiry_write_failed") as ctx: self.create()
            self.assert_safe(str(ctx.exception))
            self.assertEqual(self.config.state_file.read_bytes(), before)
            for table in ("ruby_custom_inquiries", "ruby_custom_inquiry_revisions", "ruby_custom_inquiry_receipts", "ruby_custom_inquiry_audit"):
                self.assertEqual(self.store._live.connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0], 0)
        self.assertEqual(self.create()["state"], "complete_received")

    def assert_fenced(self):
        before = self.config.state_file.read_bytes() if self.config.state_file.exists() else None
        actions = [lambda: self.create(), lambda: self.resolve(), lambda: self.store.list_ruby_inquiries(CONTEXT), lambda: self.store.create_conversation("generic-create-key-0000", b'{}'), lambda: self.store.list_conversations(), lambda: self.store.delete_conversation("synthetic-conversation-0000"), lambda: self.store._live.persist()]
        for action in actions:
            with self.assertRaisesRegex(ConversationRequestError, "fenced"): action()
        after = self.config.state_file.read_bytes() if self.config.state_file.exists() else None
        self.assertEqual(before, after)

    def reconcile(self):
        return self.store.reconcile_persistence(ISSUER, SUBJECT, inquiry_context=CONTEXT)

    def test_before_replace_failure_fences_then_authoritative_absence_unknown(self):
        before = self.config.state_file.read_bytes()
        with patch.object(core.os, "replace", side_effect=OSError(CONTACT)):
            with self.assertRaisesRegex(ConversationRequestError, "inquiry_outcome_unknown") as ctx: self.create()
        self.assert_safe(str(ctx.exception))
        self.assertEqual(self.config.state_file.read_bytes(), before)
        self.assert_fenced()
        self.assertEqual(self.reconcile()["state"], "reconciled")
        self.assertEqual(self.resolve()["state"], "unknown")
        self.assertEqual(self.store.list_ruby_inquiries(CONTEXT)["inquiries"], [])

    def test_after_replace_chmod_directory_fsync_failures_reconcile_original(self):
        for phase in ("replace", "chmod", "directory_fsync"):
            key = "failure-key-000000-" + phase
            old_replace, old_chmod, old_fsync = core.os.replace, core.os.chmod, core.os.fsync
            def replace_then_fail(source, target):
                old_replace(source, target)
                if target == self.config.state_file: raise OSError(CONTACT)
            def chmod_fail(path, mode):
                if path == self.config.state_file: raise OSError(CONTACT)
                return old_chmod(path, mode)
            def fsync_fail(fd):
                if stat.S_ISDIR(os.fstat(fd).st_mode): raise OSError(CONTACT)
                return old_fsync(fd)
            target = {"replace": "replace", "chmod": "chmod", "directory_fsync": "fsync"}[phase]
            side_effect = {"replace": replace_then_fail, "chmod": chmod_fail, "directory_fsync": fsync_fail}[phase]
            with patch.object(core.os, target, side_effect=side_effect):
                with self.assertRaisesRegex(ConversationRequestError, "outcome_unknown"): self.create(key=key)
            self.assert_fenced()
            self.reconcile()
            receipt = self.resolve(key=key)
            self.assertEqual(receipt["state"], "complete_received")
            self.assertEqual(self.create(key=key), receipt)
            self.assertEqual(self.store.get_ruby_inquiry(CONTEXT, receipt["receipt"]["inquiry_id"])["inquiry"], body())
        self.assertEqual(len(self.store.list_ruby_inquiries(CONTEXT)["inquiries"]), 3)
        self.store.create_conversation("generic-after-reconcile-0000", b'{}')
        self.assertEqual(len(self.store.list_ruby_inquiries(CONTEXT)["inquiries"]), 3)

    def test_missing_corrupt_disk_failed_fsync_revoked_policy_never_unfence(self):
        original = core.os.replace
        def fail(source, target):
            original(source, target)
            raise OSError("synthetic crash")
        with patch.object(core.os, "replace", side_effect=fail):
            with self.assertRaises(ConversationRequestError): self.create()
        committed = self.config.state_file.read_bytes()
        self.config.state_file.unlink()
        with self.assertRaisesRegex(ConversationRequestError, "reconciliation_unavailable"): self.reconcile()
        self.assert_fenced()
        self.config.state_file.write_bytes(b"not encrypted")
        self.config.state_file.chmod(0o600)
        with self.assertRaisesRegex(ConversationRequestError, "reconciliation_unavailable"): self.reconcile()
        self.assert_fenced()
        self.config.state_file.write_bytes(committed)
        with patch.object(core.os, "fsync", side_effect=OSError("unavailable")):
            with self.assertRaisesRegex(ConversationRequestError, "reconciliation_unavailable"): self.reconcile()
        self.assert_fenced()
        self.policy = None
        with self.assertRaisesRegex(ConversationRequestError, "policy_unavailable"): self.reconcile()
        self.assert_fenced()
        self.policy = POLICY
        self.reconcile()
        self.assertEqual(self.resolve()["state"], "complete_received")

    def test_generic_mutation_failure_also_fences_inquiry(self):
        self.create()
        original = core.os.replace
        def fail(source, target):
            original(source, target); raise OSError("synthetic crash")
        with patch.object(core.os, "replace", side_effect=fail):
            with self.assertRaises(OSError): self.store.create_conversation("generic-failure-0000000", b'{}')
        self.assert_fenced()
        self.reconcile()
        self.assertEqual(self.resolve()["state"], "complete_received")
        self.assertEqual(len(self.store.list_conversations()), 1)

    def test_exclusive_writer_blocks_same_and_other_process_writers_not_preflight(self):
        for kwargs in ({}, {"ruby_inquiry_policy": lambda c: POLICY}):
            with self.assertRaisesRegex(ConversationConfigurationError, "writer_unavailable"):
                ConversationStore(self.config, ISSUER, SUBJECT, **kwargs)
        with patch.dict(os.environ, {"MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT": "true"}):
            candidate = ConversationStore(self.config, ISSUER, SUBJECT)
            self.assertIsNone(candidate._lease)
            candidate.close()
        script = '''
from pathlib import Path
import sys
from conversation_store import *
p=Path(sys.argv[1])
try: ConversationStore(ConversationConfig(p/'state.enc',p/'ledger.enc',p/'synthetic.key'),'https://issuer.example.invalid','synthetic-owner')
except ConversationConfigurationError as e:
 assert str(e)=='conversation_writer_unavailable'
else: raise AssertionError('second writer opened')
'''
        subprocess.run([sys.executable, "-c", script, str(self.root)], cwd=Path(__file__).parent, check=True, capture_output=True)
        self.create(); self.store.close()
        before = self.config.state_file.read_bytes()
        with self.assertRaisesRegex(ConversationConfigurationError, "inquiry_policy_required"):
            ConversationStore(self.config, ISSUER, SUBJECT)
        self.assertEqual(before, self.config.state_file.read_bytes())
        self.store = self.open()

    def test_legacy_shared_leases_block_first_inquiry_and_constructor_failure_releases(self):
        self.store.close()
        legacy = ConversationStore(self.config, ISSUER, SUBJECT)
        try:
            with self.assertRaisesRegex(ConversationConfigurationError, "writer_unavailable"): self.open()
        finally: legacy.close()
        self.store = self.open()
        self.store.close()
        with patch.object(core.os, "replace", side_effect=OSError("startup failed")):
            with self.assertRaises(OSError): self.open()
        self.store = self.open()

    def test_receipts_not_purged_by_legacy_ninety_days_and_no_integration_enabled(self):
        receipt = self.create()
        self.store._purge_locked(100 * 365 * 24 * 3600)
        self.assertEqual(self.resolve(), receipt)
        self.assertIsNone(self.store._provider_runtime)
        self.assertFalse(self.store._notification_delivery_enabled)
        self.store.close()
        for kwargs in ({"notification_delivery_enabled": True}, {"provider_runtime": object()}):
            with self.assertRaisesRegex(ConversationConfigurationError, "synthetic_mode_required"):
                ConversationStore(self.config, ISSUER, SUBJECT, ruby_inquiry_policy=lambda c: POLICY, **kwargs)
        self.store = self.open()

    def test_deletion_marker_replay_fails_closed_until_durably_suppressed(self):
        receipt = self.create()
        conversation = self.store.create_conversation("deleted-conversation-key-0000", b'{}')
        cid = conversation["conversation_id"]
        original = core._atomic_write_private
        def fail_live(path, data, **kwargs):
            if path == self.config.state_file: raise OSError("live snapshot unavailable")
            return original(path, data, **kwargs)
        with patch.object(core, "_atomic_write_private", side_effect=fail_live):
            with self.assertRaises(OSError): self.store.delete_conversation(cid)
        self.assert_fenced()
        with patch.object(core, "_atomic_write_private", side_effect=fail_live):
            with self.assertRaisesRegex(ConversationRequestError, "reconciliation_unavailable"): self.reconcile()
        self.assert_fenced()
        self.reconcile()
        self.assertEqual(self.store.list_conversations(), [])
        self.assertEqual(self.store._live.connection.execute("SELECT COUNT(*) FROM idempotency_results WHERE resource_id=?", (cid,)).fetchone()[0], 0)
        self.assertEqual(self.resolve(), receipt)
        self.store.close()
        self.store = self.open()
        self.assertEqual(self.store.list_conversations(), [])

    def test_source_normalization_cart_blockers_safe_bounds_and_prose_preserved(self):
        value = body(); value["customization"]["cake_type"] = "basic"
        with self.assertRaises(ConversationRequestError): self.create(value)
        value = body(); value["cart"]["unresolved_blockers"] = []
        with self.assertRaises(ConversationRequestError): self.create(value)
        value = body(); value["cart"]["unresolved_blockers"].remove("packed_weight_unverified")
        with self.assertRaises(ConversationRequestError): self.create(value)
        value = body(); value["cart"]["subtotal_minor"] = 2**53
        with self.assertRaises(ConversationRequestError): self.create(value)
        value = body(); value["cart"]["unresolved_blockers"].append("Additional diagnostic prose " + "x"*400)
        receipt = self.create(value)
        self.assertEqual(self.store.get_ruby_inquiry(CONTEXT, receipt["receipt"]["inquiry_id"])["inquiry"], value)

    def test_actual_process_exit_before_and_after_snapshot_replacement(self):
        self.store.close()
        script = r'''import os,sys
from pathlib import Path
import conversation_store as core
from conversation_store import ConversationConfig,ConversationStore
from test_ruby_inquiry import ISSUER,SUBJECT,CONTEXT,POLICY,body,encoded
p=Path(sys.argv[1]);phase=sys.argv[2]
s=ConversationStore(ConversationConfig(p/'state.enc',p/'ledger.enc',p/'synthetic.key'),ISSUER,SUBJECT,ruby_inquiry_policy=lambda c:POLICY)
original=core.os.replace
def crash(source,target):
 if target==p/'state.enc' and phase=='before': os._exit(73)
 original(source,target)
 if target==p/'state.enc': os._exit(74)
core.os.replace=crash
s.create_ruby_inquiry(CONTEXT,'process-crash-key-'+phase,encoded(body()))
raise AssertionError('receipt must never return')
'''
        for phase, code in (("before", 73), ("after", 74)):
            result = subprocess.run([sys.executable, "-c", script, str(self.root), phase], cwd=Path(__file__).parent, capture_output=True)
            self.assertEqual(result.returncode, code, result.stderr)
            self.store = self.open()
            receipt = self.resolve(key="process-crash-key-" + phase)
            self.assertEqual(receipt["state"], "unknown" if phase == "before" else "complete_received")
            self.store.close()
        self.store = self.open()
        self.assertEqual(len(self.store.list_ruby_inquiries(CONTEXT)["inquiries"]), 1)

    def test_malformed_receipt_boolean_number_equality_is_not_accepted(self):
        original = self.create()
        malformed = copy.deepcopy(original)
        malformed["receipt"]["revision_number"] = True
        self.store._live.connection.execute("UPDATE ruby_custom_inquiry_receipts SET response_json=?", (json.dumps(malformed),))
        with self.assertRaisesRegex(ConversationRequestError, "receipt_binding_mismatch"):
            self.resolve()

    def test_fixture_mode_boolean_strict_and_provider_reconcile_rejected_before_io(self):
        for invalid in (False, 1, "true"):
            self.policy = replace(POLICY, synthetic_only=invalid)
            with self.assertRaisesRegex(ConversationRequestError, "policy_unavailable"): self.create()
        self.policy = POLICY
        self.store._persistence_fenced = True
        self.store._provider_anchor_path = self.root / "synthetic-unused-anchor"
        with patch.object(core, "synchronize_snapshot") as synchronize:
            with self.assertRaisesRegex(ConversationRequestError, "reconciliation_unavailable"): self.reconcile()
            synchronize.assert_not_called()
        self.assertTrue(self.store._persistence_fenced)
        self.store._provider_anchor_path = None
        self.reconcile()

    def test_inquiry_readonly_preflight_preserves_bytes_and_rejects_new_writes(self):
        self.create(); self.store.close()
        before = self.config.state_file.read_bytes(), self.config.deletion_ledger_file.read_bytes()
        with patch.dict(os.environ, {"MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT": "true"}): self.store = self.open()
        with self.assertRaisesRegex(ConversationRequestError, "inquiry_readonly"): self.resolve()
        with self.assertRaisesRegex(ConversationRequestError, "inquiry_readonly"): self.create(key="different-create-000000")
        self.assertEqual(before, (self.config.state_file.read_bytes(), self.config.deletion_ledger_file.read_bytes()))


class ReadonlyPreflightChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        key = self.root / "synthetic.key"
        key.write_text("65" * 32)
        key.chmod(0o600)
        self.config = ConversationConfig(self.root / "state.enc", self.root / "ledger.enc", key)
        self.writer = ConversationStore(self.config, ISSUER, SUBJECT, ruby_inquiry_policy=lambda c: POLICY)
        self.receipt = self.writer.create_ruby_inquiry(CONTEXT, KEY, encoded(body()))
        self.candidates = []

    def tearDown(self):
        for candidate in self.candidates:
            candidate.close()
        self.writer.close()
        self.temp.cleanup()

    def preflight(self, **kwargs):
        with patch.dict(os.environ, {"MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT": "true"}):
            candidate = ConversationStore(self.config, ISSUER, SUBJECT, **kwargs)
        self.candidates.append(candidate)
        return candidate

    def files(self):
        return {p.name: (p.read_bytes(), p.stat().st_mode, p.stat().st_ino, p.stat().st_mtime_ns)
                for p in self.root.iterdir() if p.is_file()}

    def test_active_writer_preflight_never_writes_or_locks_and_writer_stays_exclusive(self):
        import inquiry_persistence
        before = self.files()
        original_open = os.open
        def readonly_open(path, flags, *args, **kwargs):
            self.assertFalse(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            return original_open(path, flags, *args, **kwargs)
        with patch.object(inquiry_persistence, "StoreLease", side_effect=AssertionError("lease acquired")), \
             patch.object(core, "StoreLease", side_effect=AssertionError("lease acquired")), \
             patch.object(os, "open", side_effect=readonly_open), \
             patch.object(os, "fsync", side_effect=AssertionError("fsync")), \
             patch.object(os, "chmod", side_effect=AssertionError("chmod")), \
             patch.object(core, "_atomic_write_private", side_effect=AssertionError("persist")):
            candidate = self.preflight()
            self.assertEqual(candidate.list_conversations(), [])
            candidate.close()
        self.assertEqual(before, self.files())
        with self.assertRaisesRegex(ConversationConfigurationError, "writer_unavailable"):
            ConversationStore(self.config, ISSUER, SUBJECT)
        self.assertEqual(self.writer.resolve_ruby_inquiry_receipt(CONTEXT, "create", KEY, encoded(body())), self.receipt)
        self.writer.create_conversation("writer-still-active-0001", b"{}")

    def test_no_lockfile_created_if_none_exists(self):
        self.writer.close()
        lock = self.config.state_file.with_name("state.enc.writer.lock")
        lock.unlink()  # Disposable stopped fixture only; never a live lease.
        before = self.files()
        candidate = self.preflight()
        candidate.close()
        self.assertFalse(lock.exists())
        self.assertEqual(before, self.files())

    def test_all_inquiry_methods_unavailable_with_or_without_policy(self):
        inquiry_id = self.receipt["receipt"]["inquiry_id"]
        resolver = Mock(return_value=POLICY)
        for kwargs in ({}, {"ruby_inquiry_policy": resolver}):
            candidate = self.preflight(**kwargs)
            calls = (
                lambda: candidate.create_ruby_inquiry(CONTEXT, KEY, encoded(body())),
                lambda: candidate.revise_ruby_inquiry(CONTEXT, inquiry_id, KEY, b"{}"),
                lambda: candidate.resolve_ruby_inquiry_receipt(CONTEXT, "create", KEY, encoded(body())),
                lambda: candidate.get_ruby_inquiry(CONTEXT, inquiry_id),
                lambda: candidate.list_ruby_inquiries(CONTEXT),
                lambda: candidate.list_ruby_inquiry_audit(CONTEXT, inquiry_id),
            )
            for call in calls:
                with self.assertRaisesRegex(ConversationRequestError, "inquiry_readonly"):
                    call()
        resolver.assert_not_called()

    def test_generic_mutations_and_deserialize_cannot_unseal_readonly_connections(self):
        conversation = self.writer.create_conversation("preflight-existing-0001", b"{}")
        cid = conversation["conversation_id"]
        candidate = self.preflight()
        before_disk = self.files()
        before_memory = [snapshot.connection.serialize() for snapshot in (candidate._live, candidate._ledger)]
        # Preserve pre-existing legacy idempotent read semantics.
        self.assertEqual(candidate.create_conversation("preflight-existing-0001", b"{}"), conversation)
        for call in (
            lambda: candidate.create_conversation("preflight-new-create-0001", b"{}"),
            lambda: candidate.submit_message(cid, "preflight-new-message-0001", b'{"body":"must not store"}'),
            lambda: candidate.delete_conversation(cid),
            lambda: candidate._purge_locked(100 * 365 * 24 * 3600),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                call()
            for snapshot, before in zip((candidate._live, candidate._ledger), before_memory):
                self.assertEqual(snapshot.connection.serialize(), before)
                self.assertEqual(snapshot.connection.execute("PRAGMA query_only").fetchone()[0], 1)
        for snapshot in (candidate._live, candidate._ledger):
            snapshot.connection.deserialize(snapshot.connection.serialize())
            with self.assertRaises(sqlite3.OperationalError):
                snapshot.connection.execute("CREATE TABLE forbidden(value TEXT)")
            with self.assertRaisesRegex(ConversationRequestError, "conversation_readonly_preflight"):
                snapshot.persist()
        for fenced in (False, True):
            candidate._persistence_fenced = fenced
            with patch.object(core, "synchronize_snapshot", side_effect=AssertionError("recovery IO")):
                with self.assertRaisesRegex(ConversationRequestError, "conversation_readonly_preflight"):
                    candidate.reconcile_persistence(ISSUER, SUBJECT)
        self.assertEqual(before_disk, self.files())

    def test_provider_notification_configuration_never_dispatches_or_changes_recovery_state(self):
        conversation = self.writer.create_conversation("preflight-provider-0001", b"{}")
        message = self.writer.submit_message(conversation["conversation_id"], "preflight-provider-msg-0001", b'{"body":"synthetic"}')
        self.writer._live.connection.execute("UPDATE response_states SET state='responding',error_code=NULL")
        self.writer._live.persist()
        before = self.files()
        runtime, deliver = Mock(), Mock()
        candidate = self.preflight(provider_runtime=runtime, notification_delivery_enabled=True)
        self.assertIsNone(candidate._provider_anchor_path)
        self.assertFalse(candidate.dispatch_one_response(now=1234))
        self.assertFalse(candidate.dispatch_one_notification(deliver, now=1234, retry_seconds=900))
        runtime.assert_not_called()
        self.assertEqual(runtime.mock_calls, [])
        deliver.assert_not_called()
        self.assertEqual(candidate._live.connection.execute("SELECT state FROM response_states WHERE message_id=?", (message["message_id"],)).fetchone()[0], "responding")
        self.assertEqual(before, self.files())

    def test_durable_deletion_ahead_of_live_replayed_only_in_memory(self):
        conversation = self.writer.create_conversation("preflight-deletion-0001", b"{}")
        cid = conversation["conversation_id"]
        self.writer.submit_message(cid, "preflight-deletion-msg-0001", b'{"body":"deleted synthetic sentinel"}')
        original = core._atomic_write_private
        def fail_live(path, *args, **kwargs):
            if path == self.config.state_file:
                raise OSError("interrupted live delete")
            return original(path, *args, **kwargs)
        with patch.object(core, "_atomic_write_private", side_effect=fail_live):
            with self.assertRaises(OSError):
                self.writer.delete_conversation(cid)
        before = self.files()
        candidate = self.preflight()
        self.assertEqual(candidate.list_conversations(), [])
        with self.assertRaisesRegex(ConversationRequestError, "not_found"):
            candidate.list_messages(cid)
        self.assertEqual(candidate._live.connection.execute("SELECT COUNT(*) FROM idempotency_results WHERE resource_id=?", (cid,)).fetchone()[0], 0)
        self.assertEqual(before, self.files())
        self.assertTrue(self.writer._persistence_fenced)

    def test_snapshot_replacement_during_capture_fails_closed(self):
        import inquiry_persistence
        original_read = os.read
        changed = False
        def replace_during_read(fd, size):
            nonlocal changed
            result = original_read(fd, size)
            if not changed:
                changed = True
                self.writer.create_conversation("concurrent-replace-0001", b"{}")
            return result
        with patch.object(inquiry_persistence.os, "read", side_effect=replace_during_read):
            with self.assertRaisesRegex(ConversationConfigurationError, "preflight_snapshot_changed"):
                self.preflight()
        self.assertEqual(len(self.preflight().list_conversations()), 1)

    def test_missing_corrupt_insecure_and_symlink_snapshots_fail_closed(self):
        self.writer.close()
        for path in (self.config.state_file, self.config.deletion_ledger_file):
            original = path.read_bytes()
            for state in ("missing", "corrupt", "insecure", "symlink"):
                with self.subTest(path=path.name, state=state):
                    if state == "missing":
                        path.unlink()
                    elif state == "corrupt":
                        path.write_bytes(b"not encrypted")
                    elif state == "insecure":
                        path.chmod(0o644)
                    else:
                        path.unlink()
                        path.symlink_to(self.config.key_file)
                    with self.assertRaises(ConversationConfigurationError):
                        self.preflight()
                    if path.is_symlink():
                        path.unlink()
                    path.write_bytes(original)
                    path.chmod(0o600)

    def test_preflight_other_process_active_writer_audit_denies_all_write_syscalls(self):
        before = self.files()
        script = r'''import os,sys
from pathlib import Path
from conversation_store import ConversationConfig,ConversationStore
from test_ruby_inquiry import ISSUER,SUBJECT
p=Path(sys.argv[1])
def audit(event,args):
 if event=='open':
  mode=args[1]; flags=args[2]
  if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
   raise AssertionError('write open in readonly preflight')
 if event in ('os.chmod','os.rename','os.remove','os.rmdir','os.mkdir','os.link','os.symlink','os.truncate'):
  raise AssertionError('filesystem mutation in readonly preflight')
sys.addaudithook(audit)
os.environ['MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT']='true'
s=ConversationStore(ConversationConfig(p/'state.enc',p/'ledger.enc',p/'synthetic.key'),ISSUER,SUBJECT)
assert s._lease is None
assert s.list_conversations()==[]
s.close()
'''
        result = subprocess.run([sys.executable, "-B", "-c", script, str(self.root)], cwd=Path(__file__).parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.files())


if __name__ == "__main__": unittest.main()

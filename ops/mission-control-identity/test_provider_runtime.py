"""Offline MC-010 checks: all transports mocked; no provider credentials used."""
import json
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

from provider_runtime import ProviderPolicy, ProviderRuntime, ProviderFailure, OpenAITransport, budget_day
from conversation_store import ConversationStore
import test_conversation_store as fixtures
from test_conversation_store import ISSUER, SUBJECT


def reply():
    return {"model": "reviewed-model", "status": "completed",
            "usage": {"input_tokens": 100, "output_tokens": 20},
            "output": [{"type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": "Advisory only."}]}]}


class RuntimeChecks(unittest.TestCase):
    def runtime(self, count=100):
        return ProviderRuntime(ProviderPolicy("reviewed-model", 400000, 1600000, 4102444800),
                               Mock(return_value=count), Mock(return_value=reply()))

    def test_caps_and_payload(self):
        runtime = self.runtime()
        payload = runtime.prepare("synthetic message", int(time.time()))
        runtime.count_input.assert_not_called()
        self.assertEqual(payload["max_output_tokens"], 750)
        self.assertEqual(payload["tools"], [])
        self.assertEqual(payload["tool_choice"], "none")
        self.assertFalse(payload["store"])
        self.assertEqual(runtime.complete(payload), "Advisory only.")
        runtime.send.assert_called_once_with(payload, timeout_seconds=30, max_retries=0)

    def test_input_rejected_before_inference(self):
        for count in (4001, 0, -1, True, None, "4000"):
            runtime = self.runtime(count)
            with self.assertRaises(ProviderFailure):
                runtime.complete(runtime.prepare("test", int(time.time())))
            runtime.send.assert_not_called()
        runtime = self.runtime(4000)
        self.assertEqual(runtime.complete(runtime.prepare("test", int(time.time()))), "Advisory only.")

    def test_policy_expiry_and_unknown_rates_fail_closed(self):
        for policy in (ProviderPolicy("m", 1, 1, 1), ProviderPolicy("", 1, 1, 4102444800),
                       ProviderPolicy("m", 0, 1, 4102444800)):
            with self.assertRaises(ProviderFailure):
                ProviderRuntime(policy, Mock(), Mock()).prepare("test", 2)

    def test_invalid_outputs_are_not_persistable(self):
        invalid = [dict(reply(), status="incomplete"), dict(reply(), model="other"),
                   dict(reply(), output=[{"type": "function_call"}]),
                   dict(reply(), usage={"input_tokens": 4001, "output_tokens": 2}),
                   dict(reply(), usage={"input_tokens": 2, "output_tokens": 751})]
        for result in invalid:
            runtime = self.runtime()
            runtime.send.return_value = result
            with self.assertRaises(ProviderFailure):
                runtime.complete(runtime.prepare("test", int(time.time())))

    def test_fixed_transport_origin_count_and_no_redirect(self):
        transport = OpenAITransport("synthetic-key")
        connection = Mock()
        response = connection.getresponse.return_value
        response.status = 200
        response.read1.side_effect = [b'{"object":"response.input_tokens","input_tokens":123}', b'']
        payload = self.runtime().prepare("test", int(time.time()))
        with patch("provider_runtime.http.client.HTTPSConnection", return_value=connection) as factory:
            self.assertEqual(transport.count_input(payload), 123)
            factory.assert_called_once_with("api.openai.com", timeout=30)
        args = connection.request.call_args.args
        self.assertEqual(args[1], "/v1/responses/input_tokens")
        self.assertEqual(json.loads(args[2])["instructions"], payload["instructions"])
        response.status = 302
        with patch("provider_runtime.http.client.HTTPSConnection", return_value=connection):
            with self.assertRaisesRegex(ProviderFailure, "provider_transport_failed"):
                transport.send(payload, timeout_seconds=30, max_retries=0)
        self.assertEqual(connection.request.call_count, 2)
        self.assertEqual(connection.close.call_count, 2)


class StoreRuntimeChecks(unittest.TestCase):
    setUp = fixtures.ConversationStoreChecks.setUp
    tearDown = fixtures.ConversationStoreChecks.tearDown

    def store(self, runtime=None):
        return ConversationStore(self.config, ISSUER, SUBJECT, provider_runtime=runtime)

    def message(self, store, suffix="one"):
        conversation = store.create_conversation("create-provider-" + suffix, b"{}")
        message = store.submit_message(conversation["conversation_id"], "submit-provider-" + suffix,
                                       b'{"body":"synthetic advice request"}')
        return conversation["conversation_id"], message

    def test_default_disabled(self):
        store = self.store()
        _, message = self.message(store)
        self.assertEqual(message["response_state"], "unavailable")
        self.assertFalse(store.dispatch_one_response(now=int(time.time())))

    def test_readonly_candidate_never_dispatches_or_rewrites(self):
        runtime = RuntimeChecks().runtime()
        store = self.store(runtime)
        self.message(store)
        before = self.config.state_file.read_bytes()
        with patch.dict(os.environ, {"MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT": "true"}):
            candidate = self.store(runtime)
        self.assertFalse(candidate.dispatch_one_response(now=int(time.time())))
        self.assertEqual(before, self.config.state_file.read_bytes())
        runtime.count_input.assert_not_called()

    def test_unknown_budget_carries_to_next_day(self):
        runtime = RuntimeChecks().runtime()
        runtime.policy = ProviderPolicy("reviewed-model", 1000000000, 1000000000, 4102444800)
        runtime.send.side_effect = TimeoutError()
        store = self.store(runtime)
        self.message(store, "one")
        now = int(time.time())
        store.dispatch_one_response(now=now)
        _, second = self.message(store, "two")
        store.dispatch_one_response(now=now + 86400)
        runtime.send.assert_called_once()
        self.assertEqual(store._live.connection.execute(
            "SELECT error_code FROM response_states WHERE message_id=?", (second["message_id"],)).fetchone()[0],
            "provider_daily_limit")

    def test_jst_day_boundary(self):
        self.assertEqual(budget_day(0), "1970-01-01")
        self.assertEqual(budget_day(15 * 3600), "1970-01-02")

    def test_durable_response_idempotency_and_encryption(self):
        runtime = RuntimeChecks().runtime()
        store = self.store(runtime)
        cid, message = self.message(store)
        self.assertEqual(message["response_state"], "queued")
        self.assertTrue(store.dispatch_one_response(now=int(time.time())))
        self.assertFalse(store.dispatch_one_response(now=int(time.time())))
        self.assertEqual(store.get_response_state(cid, message["message_id"])["state"], "complete")
        self.assertEqual(len(self.store().list_messages(cid)), 2)
        self.assertNotIn(b"Advisory only.", self.config.state_file.read_bytes())
        runtime.send.assert_called_once()

    def test_failure_keeps_reservation_across_restart_and_deletion(self):
        runtime = RuntimeChecks().runtime()
        runtime.send.side_effect = TimeoutError("secret must never persist")
        store = self.store(runtime)
        cid, message = self.message(store)
        store.dispatch_one_response(now=int(time.time()))
        self.assertEqual(store.get_response_state(cid, message["message_id"])["error_code"], "provider_outcome_unknown")
        store.delete_conversation(cid)
        reopened = self.store(runtime)
        self.assertFalse(reopened.dispatch_one_response(now=int(time.time())))
        self.assertEqual(reopened._live.connection.execute("SELECT state FROM provider_attempts").fetchone()[0], "unknown")
        runtime.send.assert_called_once()

    def test_no_network_before_durable_claim(self):
        runtime = RuntimeChecks().runtime()
        store = self.store(runtime)
        self.message(store)
        with patch.object(store._live, "persist", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                store.dispatch_one_response(now=int(time.time()))
        runtime.count_input.assert_not_called()
        runtime.send.assert_not_called()

    def test_atomic_budget_concurrent_dispatch(self):
        runtime = RuntimeChecks().runtime()
        runtime.policy = ProviderPolicy("reviewed-model", 1000000000, 1000000000, 4102444800)
        store = self.store(runtime)
        self.message(store, "one")
        self.message(store, "two")
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: store.dispatch_one_response(now=int(time.time())), range(2)))
        self.assertEqual(runtime.send.call_count, 1)
        rows = store._live.connection.execute("SELECT error_code FROM response_states WHERE state='failed'").fetchall()
        self.assertEqual([row[0] for row in rows], ["provider_daily_limit"])

    def test_restart_inflight_is_never_replayed(self):
        runtime = RuntimeChecks().runtime()
        store = self.store(runtime)
        cid, message = self.message(store)
        original = store._live.persist
        calls = []
        def persist():
            calls.append(1)
            if len(calls) == 2:
                raise OSError("final persist failure")
            original()
        with patch.object(store._live, "persist", side_effect=persist):
            with self.assertRaises(OSError):
                store.dispatch_one_response(now=int(time.time()))
        reopened = self.store(runtime)
        self.assertFalse(reopened.dispatch_one_response(now=int(time.time())))
        self.assertEqual(reopened.get_response_state(cid, message["message_id"])["state"], "failed")
        runtime.send.assert_called_once()


if __name__ == "__main__":
    unittest.main()

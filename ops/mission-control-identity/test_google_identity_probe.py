"""Offline security checks for the inactive Google identity probe."""

from __future__ import annotations

import base64
import contextlib
import datetime
import hashlib
import http.client
import io
import json
import sys
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parent))
import google_identity_probe as probe  # noqa: E402
import google_oidc_config as config  # noqa: E402


class FakeRaw:
    def __init__(self, value: bytes) -> None:
        self.value = value

    def read(self, limit: int, decode_content: bool = False) -> bytes:
        return self.value[:limit]


class FakeResponse:
    def __init__(self, status: int, value: bytes) -> None:
        self.status_code = status
        self.raw = FakeRaw(value)
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, status: int = 200, value: bytes = b'{}') -> None:
        self.response = FakeResponse(status, value)
        self.post_args: tuple | None = None
        self.trust_env = True
        self.max_redirects = 30

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def post(self, *args, **kwargs):
        self.post_args = (args, kwargs)
        return self.response

    def close(self) -> None:
        return None


class ConfigAndFlowChecks(unittest.TestCase):
    def test_oauth_flow_ttl_is_fifteen_minutes(self) -> None:
        self.assertEqual(probe.FLOW_SECONDS, 15 * 60)

    def test_config_is_inactive_by_default(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(config.GoogleOidcConfigurationError, "google_oidc_inactive"):
                config.GoogleOidcConfig.from_environment()

    def test_config_rejects_wrong_issuer_before_secret_access(self) -> None:
        with mock.patch.dict("os.environ", {"MISSION_CONTROL_GOOGLE_OIDC_ENABLED": "true"}, clear=True):
            with mock.patch.object(config, "_protected_file") as protected:
                with self.assertRaisesRegex(config.GoogleOidcConfigurationError, "issuer_invalid"):
                    config.GoogleOidcConfig.from_environment()
                protected.assert_not_called()

    def test_flow_is_bounded_single_use_and_expires(self) -> None:
        store = probe.FlowStore()
        self.assertTrue(store.empty())
        flow = probe.PendingFlow(b"hash", "nonce", "verifier", time.monotonic())
        self.assertTrue(store.put("state", flow))
        self.assertFalse(store.empty())
        self.assertEqual(store.take("state"), flow)
        self.assertTrue(store.empty())
        self.assertIsNone(store.take("state"))
        old = probe.PendingFlow(b"hash", "nonce", "verifier", time.monotonic() - probe.FLOW_SECONDS - 1)
        self.assertTrue(store.put("old", old))
        self.assertIsNone(store.take("old"))

    def test_pkce_challenge_uses_sha256(self) -> None:
        verifier = "a" * 64
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(probe._challenge(verifier), expected)

    def test_certificate_fetch_is_pinned_bounded_and_refuses_redirect(self) -> None:
        class CertificateSession:
            def __init__(self, status: int, value: bytes) -> None:
                self.response = FakeResponse(status, value)
                self.call = None

            def get(self, *args, **kwargs):
                self.call = (args, kwargs)
                return self.response

            def close(self) -> None:
                return None

        session = CertificateSession(200, b"{}")
        request = probe.BoundedGoogleRequest(session=session)
        with self.assertRaises(ValueError):
            request("https://example.com/certs")
        result = request("https://www.googleapis.com/oauth2/v1/certs")
        self.assertEqual(result.status, 200)
        self.assertEqual(result.data, b"{}")
        self.assertFalse(session.call[1]["allow_redirects"])
        self.assertTrue(session.response.closed)
        oversized = CertificateSession(200, b"x" * (probe.MAX_CERTIFICATE_RESPONSE_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "too_large"):
            probe.BoundedGoogleRequest(session=oversized)("https://www.googleapis.com/oauth2/v1/certs")


class TokenClaimChecks(unittest.TestCase):
    @staticmethod
    def token(alg: str = "RS256") -> str:
        header = base64.urlsafe_b64encode(json.dumps({"alg": alg, "kid": "kid"}).encode()).rstrip(b"=").decode()
        return header + ".payload.signature"

    def test_valid_claims_require_exact_issuer_nonce_presenter_and_subject(self) -> None:
        claims = {
            "iss": probe.ISSUER,
            "azp": probe.CLIENT_ID,
            "nonce": "nonce",
            "sub": "12345",
            "email": "synthetic-email@example.test",
            "email_verified": True,
            "name": "Synthetic Person",
        }
        session = FakeSession()
        with mock.patch.object(probe.google_id_token, "verify_oauth2_token", return_value=claims):
            self.assertEqual(probe._verified_subject(self.token(), "nonce", session), "12345")
            with self.assertRaisesRegex(ValueError, "nonce_mismatch"):
                probe._verified_subject(self.token(), "other", session)
            for key, value in (("iss", "accounts.google.com"), ("azp", "wrong"), ("sub", ""), ("nbf", time.time() + 60)):
                with self.subTest(key=key):
                    bad = {**claims, key: value}
                    with mock.patch.object(probe.google_id_token, "verify_oauth2_token", return_value=bad):
                        with self.assertRaises(ValueError):
                            probe._verified_subject(self.token(), "nonce", session)

    def test_algorithm_and_signature_failure_are_rejected(self) -> None:
        session = FakeSession()
        with mock.patch.object(probe.google_id_token, "verify_oauth2_token") as verify:
            with self.assertRaisesRegex(ValueError, "algorithm_invalid"):
                probe._verified_subject(self.token("none"), "nonce", session)
            verify.assert_not_called()
            verify.side_effect = ValueError("invalid signature")
            with self.assertRaises(ValueError):
                probe._verified_subject(self.token(), "nonce", session)

    def test_real_google_auth_verifier_with_synthetic_certificate(self) -> None:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "offline-test")])
        now = datetime.datetime.now(datetime.timezone.utc)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .sign(private_key, hashes.SHA256())
        )
        pem = certificate.public_bytes(serialization.Encoding.PEM).decode("ascii")

        class CertSession(FakeSession):
            def get(self, *_args, **_kwargs):
                return FakeResponse(200, json.dumps({"kid": pem}).encode("utf-8"))

        def encoded(value: dict) -> str:
            return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=").decode()

        def signed_token(**overrides) -> str:
            claims = {
                "iss": probe.ISSUER,
                "aud": probe.CLIENT_ID,
                "azp": probe.CLIENT_ID,
                "sub": "12345",
                "nonce": "nonce",
                "iat": int(time.time()) - 1,
                "exp": int(time.time()) + 60,
            }
            claims.update(overrides)
            unsigned = encoded({"alg": "RS256", "kid": "kid"}) + "." + encoded(claims)
            signature = private_key.sign(unsigned.encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
            return unsigned + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

        session = CertSession()
        self.assertEqual(probe._verified_subject(signed_token(), "nonce", session), "12345")
        for claims in ({"aud": "wrong"}, {"exp": int(time.time()) - 60}, {"iss": "https://example.com"}):
            with self.subTest(claims=claims), self.assertRaises(Exception):
                probe._verified_subject(signed_token(**claims), "nonce", session)
        forged = signed_token()
        unsigned, signature = forged.rsplit(".", 1)
        altered = unsigned + "." + ("A" if signature[0] != "A" else "B") + signature[1:]
        with self.assertRaises(Exception):
            probe._verified_subject(altered, "nonce", session)


class ProbeHttpChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), probe.ProbeHandler)
        self.server.flows = probe.FlowStore()
        self.server.secret_file = mock.Mock(read_text=mock.Mock(return_value="synthetic-secret"))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, path: str, *, method: str = "GET", cookie: str = "") -> tuple[int, dict[str, str], str]:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        headers = {"Host": "miscon.phireij.cloud"}
        if cookie:
            headers["Cookie"] = cookie
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode("utf-8")
        connection.close()
        return result

    def test_start_has_pkce_state_nonce_and_host_cookie(self) -> None:
        status, headers, body = self.request("/auth/google/start")
        self.assertEqual(status, 302)
        self.assertEqual(body, "Continue to Google")
        self.assertEqual(headers["Cache-Control"], "no-store, no-cache, max-age=0, must-revalidate")
        self.assertEqual(headers["Pragma"], "no-cache")
        self.assertEqual(headers["Expires"], "0")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(headers["Content-Security-Policy"], "default-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.assertIn("Secure; HttpOnly; SameSite=None", headers["Set-Cookie"])
        self.assertNotIn("Domain=", headers["Set-Cookie"])
        parsed = urlsplit(headers["Location"])
        self.assertEqual(parsed.netloc, "accounts.google.com")
        values = parse_qs(parsed.query)
        self.assertEqual(values["redirect_uri"], [probe.REDIRECT_URI])
        self.assertEqual(values["scope"], ["openid email"])
        self.assertEqual(values["code_challenge_method"], ["S256"])
        self.assertEqual(values["response_type"], ["code"])
        self.assertTrue(values["state"][0] and values["nonce"][0])

    def test_start_accepts_only_a_bounded_opaque_cache_buster(self) -> None:
        self.assertEqual(self.request("/auth/google/start?attempt=mc_r3_retry_20261027")[0], 302)
        for query in ("?attempt=short", "?attempt=mc-r3-retry-20261027&extra=value", "?other=mc-r3-retry-20261027"):
            with self.subTest(query=query):
                self.assertEqual(self.request("/auth/google/start" + query)[0], 404)

    def test_callback_refuses_unbound_state_and_replay_without_network(self) -> None:
        with mock.patch.object(probe.requests, "Session") as session:
            self.assertEqual(self.request("/auth/google/callback?state=unknown&code=synthetic")[0], 401)
            browser = "synthetic-browser"
            flow = probe.PendingFlow(hashlib.sha256(browser.encode()).digest(), "nonce", "verifier", time.monotonic())
            self.server.flows.put("state", flow)
            path = "/auth/google/callback?state=state&code=synthetic"
            self.assertEqual(self.request(path, cookie=f"{probe.COOKIE_NAME}=wrong")[0], 401)
            self.assertEqual(self.request(path, cookie=f"{probe.COOKIE_NAME}={browser}")[0], 401)
            session.assert_not_called()

    def test_callback_without_a_browser_cookie_uses_the_single_use_server_flow(self) -> None:
        self.server.flows.put("state", probe.PendingFlow(b"hash", "nonce", "verifier", time.monotonic()))
        session = FakeSession(302)
        with mock.patch.object(probe.requests, "Session", return_value=session):
            self.assertEqual(self.request("/auth/google/callback?state=state&code=synthetic")[0], 502)
        self.assertIsNotNone(session.post_args)

    def test_callback_rejects_token_redirect_and_hides_code(self) -> None:
        browser = "synthetic-browser"
        self.server.flows.put("state", probe.PendingFlow(hashlib.sha256(browser.encode()).digest(), "nonce", "verifier", time.monotonic()))
        session = FakeSession(302)
        with mock.patch.object(probe.requests, "Session", return_value=session):
            with contextlib.redirect_stderr(io.StringIO()) as output:
                status, _headers, body = self.request("/auth/google/callback?state=state&code=synthetic-code", cookie=f"{probe.COOKIE_NAME}={browser}")
        self.assertEqual(status, 502)
        self.assertNotIn("synthetic-code", body + output.getvalue())
        self.assertIn("mission_control_google_probe_stage=failed_token_exchange_unexpected_status", output.getvalue())
        self.assertFalse(session.post_args[1]["allow_redirects"])
        self.assertFalse(session.trust_env)
        self.assertEqual(session.max_redirects, 0)
        self.assertTrue(session.response.closed)

    def test_token_exchange_failure_stages_are_allowlisted_and_non_sensitive(self) -> None:
        self.assertEqual(probe._token_exchange_failure_stage(400), "token_exchange_request_rejected")
        self.assertEqual(probe._token_exchange_failure_stage(401), "token_exchange_client_rejected")
        self.assertEqual(probe._token_exchange_failure_stage(403), "token_exchange_client_rejected")
        self.assertEqual(probe._token_exchange_failure_stage(429), "token_exchange_rate_limited")
        self.assertEqual(probe._token_exchange_failure_stage(500), "token_exchange_google_unavailable")
        self.assertEqual(probe._token_exchange_failure_stage(302), "token_exchange_unexpected_status")

    def test_success_hides_identity_details_without_session_or_token(self) -> None:
        browser = "synthetic-browser"
        self.server.flows.put("state", probe.PendingFlow(hashlib.sha256(browser.encode()).digest(), "nonce", "verifier", time.monotonic()))
        session = FakeSession(200, b'{"id_token":"synthetic-id-token"}')
        with mock.patch.object(probe.requests, "Session", return_value=session):
            with mock.patch.object(probe, "_verified_subject", return_value="synthetic-subject@example.test"):
                status, headers, body = self.request("/auth/google/callback?state=state&code=synthetic-code", cookie=f"{probe.COOKIE_NAME}={browser}")
        self.assertEqual(status, 200)
        self.assertIn("No Mission Control session was created", body)
        self.assertIn("Identity details are not displayed or retained", body)
        self.assertNotIn("synthetic-subject@example.test", body)
        self.assertNotIn("synthetic-id-token", body)
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        self.assertNotIn("mission_control:conversation", body)

    def test_opt_in_enrollment_receives_only_the_verified_subject_and_grants_no_session(self) -> None:
        browser = "synthetic-browser"
        self.server.flows.put("state", probe.PendingFlow(hashlib.sha256(browser.encode()).digest(), "nonce", "verifier", time.monotonic()))
        self.server.subject_enrollment = mock.Mock()
        session = FakeSession(200, b'{"id_token":"synthetic-id-token"}')
        with mock.patch.object(probe.requests, "Session", return_value=session):
            with mock.patch.object(probe, "_verified_subject", return_value="synthetic-subject"):
                status, _headers, body = self.request("/auth/google/callback?state=state&code=synthetic-code", cookie=f"{probe.COOKIE_NAME}={browser}")
        self.assertEqual(status, 200)
        self.server.subject_enrollment.enroll.assert_called_once_with("synthetic-subject")
        self.assertIn("protected subject digest was enrolled", body)
        self.assertIn("No Mission Control session was created", body)
        self.assertNotIn("synthetic-subject", body)

    def test_opt_in_r3_runtime_receives_the_verified_subject_only_and_grants_no_session(self) -> None:
        browser = "synthetic-browser"
        self.server.flows.put("state", probe.PendingFlow(hashlib.sha256(browser.encode()).digest(), "nonce", "verifier", time.monotonic()))
        self.server.r3_metadata_runtime = mock.Mock()
        session = FakeSession(200, b'{"id_token":"synthetic-id-token"}')
        with mock.patch.object(probe.requests, "Session", return_value=session):
            with mock.patch.object(probe, "_verified_subject", return_value="synthetic-subject"):
                status, _headers, body = self.request("/auth/google/callback?state=state&code=synthetic-code", cookie=f"{probe.COOKIE_NAME}={browser}")
        self.assertEqual(status, 200)
        self.server.r3_metadata_runtime.attest_and_write.assert_called_once_with("synthetic-subject")
        self.assertIn("R3 reauthentication metadata was recorded with no action authority", body)
        self.assertIn("No Mission Control session was created", body)
        self.assertNotIn("synthetic-subject", body)

    def test_health_and_mutations_have_no_authority(self) -> None:
        self.assertIn("authority_effect=none", self.request("/auth/google/healthz")[2])
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            with self.subTest(method=method):
                self.assertEqual(self.request("/auth/google/start", method=method)[0], 405)

    def test_runtime_requires_both_default_off_gates(self) -> None:
        with mock.patch.dict("os.environ", {"MISSION_CONTROL_GOOGLE_PROBE_ENABLED": "true", "MISSION_CONTROL_GOOGLE_CLIENT_ID": probe.CLIENT_ID, "MISSION_CONTROL_GOOGLE_CLIENT_SECRET_FILE": "/tmp/secret", "MISSION_CONTROL_R3_ATTESTATION_RUNTIME_ENABLED": "true"}, clear=True):
            with mock.patch.object(probe, "_protected_file", return_value=mock.Mock()):
                with mock.patch.object(probe.R3AttestationHandoff, "from_environment", side_effect=ValueError("handoff_inactive")):
                    with self.assertRaisesRegex(SystemExit, "handoff_inactive"):
                        probe.main()


if __name__ == "__main__":
    unittest.main()

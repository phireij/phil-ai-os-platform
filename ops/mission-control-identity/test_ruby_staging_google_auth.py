"""Actual backend tests with synthetic signing keys and all HTTP send mocked.

Socket creation, connection helpers and DNS are denied before backend imports.
No credential files/environment, live Google requests, listener or container.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import formatdate
import inspect
import io
import json
import socket
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

import requests

# Block all external effects even during backend import and test collection.
_guards = [patch.object(socket, name, side_effect=AssertionError("network_forbidden"))
           for name in ("socket", "create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex")]
def _deny_network(*_args, **_kwargs):
    raise AssertionError("network_forbidden")


_guards.append(patch.object(requests.Session, "send", new=_deny_network))
for _guard in _guards:
    _guard.start()

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from google.auth import crypt, jwt
from urllib3._collections import HTTPHeaderDict

import ruby_staging_google_auth as backend
from ruby_staging_google_auth import (
    AuthenticationConfigurationError, AuthenticationRejected,
    CERTIFICATE_URL, TOKEN_URL, StagingGoogleOwnerAuthenticator,
)
from ruby_staging_id_token import VerifiedOwnerClaims
from ruby_staging_lifecycle import CodeExchangeInputs


NOW = 1700000000
ORIGIN = "https://staging.example.test"
CLIENT = "synthetic-auth.apps.googleusercontent.com"
OWNER = "synthetic-owner"
SECRET = "synthetic-constructor-secret-not-real"
FLOW = CodeExchangeInputs("N" * 64, "V" * 64)


class Raw:
    def __init__(self, body, headers):
        self.body = io.BytesIO(body)
        self.headers = HTTPHeaderDict()
        for key, value in headers:
            self.headers.add(key, value)
        self.closed = False
        self.released = False
        self.reads = []
        self.on_read = None

    def read1(self, count, *, decode_content):
        self.reads.append((count, decode_content))
        if self.on_read:
            self.on_read()
        return self.body.read(count)

    def close(self):
        self.closed = True
        self.body.close()

    def release_conn(self):
        self.released = True


class StagingGoogleAuthenticatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private = cls.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption())
        cls.signer = crypt.RSASigner.from_string(private, key_id="synthetic-cert")

    def setUp(self):
        self.wall, self.mono = NOW, 100.0
        self.replies, self.sent, self.instances = [], [], []
        for p in (patch.object(requests.Session, "send", autospec=True, side_effect=self.send),
                  patch.object(backend.time, "monotonic", side_effect=lambda: self.mono),
                  patch("google.auth._helpers.utcnow", side_effect=lambda:
                        datetime.fromtimestamp(self.wall, timezone.utc).replace(tzinfo=None))):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(lambda: [instance.close() for instance in self.instances])

    def send(self, session, request, **kwargs):
        self.sent.append((session, request, kwargs))
        if not self.replies:
            raise AssertionError("unexpected_http_request")
        response = self.replies.pop(0)
        if isinstance(response, Exception):
            raise response
        response.request = request
        return response

    def make(self, **changes):
        options = dict(origin=ORIGIN, client_id=CLIENT, owner_subject=OWNER, client_secret=SECRET,
                       max_cache_seconds=300, enabled=True, clock=lambda: self.wall)
        options.update(changes)
        result = StagingGoogleOwnerAuthenticator(**options)
        self.instances.append(result)
        return result

    def cert(self, begin=NOW-3600, end=NOW+3600, key=None):
        key = key or self.key
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic-backend-test")])
        return (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(1).not_valid_before(datetime.fromtimestamp(begin, timezone.utc))
                .not_valid_after(datetime.fromtimestamp(end, timezone.utc)).sign(key, hashes.SHA256())
                .public_bytes(serialization.Encoding.PEM).decode("ascii"))

    def token(self, signer=None, **changes):
        claims = dict(iss="https://accounts.google.com", aud=CLIENT, sub=OWNER,
                      nonce=FLOW.nonce, iat=NOW-1, exp=NOW+3600)
        claims.update(changes)
        return jwt.encode(signer or self.signer, claims).decode("ascii")

    def response(self, url=TOKEN_URL, body=None, headers=None, status=200):
        response = requests.Response()
        response.status_code, response.url = status, url
        response.raw = Raw(body if body is not None else json.dumps({"id_token": self.token()}).encode(),
                           headers if headers is not None else [("Content-Type", "application/json")])
        return response

    def cert_response(self, pem=None, extra=(), **kw):
        headers = [("Content-Type", "application/json; charset=utf-8"),
                   ("Cache-Control", "public, max-age=300"), ("Date", formatdate(self.wall, usegmt=True))]
        headers.extend(extra)
        return self.response(url=CERTIFICATE_URL, body=json.dumps({"synthetic-cert": pem or self.cert()}).encode(),
                             headers=headers, **kw)

    def queue(self, token=None, cert=True):
        token_response = self.response(body=json.dumps({"id_token": token or self.token(),
                                                      "token_type": "Bearer", "access_token": "synthetic-unused"}).encode())
        self.replies.append(token_response)
        if cert:
            cert_response = self.cert_response()
            self.replies.append(cert_response)
            return token_response, cert_response
        return (token_response,)

    def authenticate(self, auth, code="synthetic-code+/&=", flow=FLOW):
        return auth.authenticate(code=code, flow=flow)

    def reject(self, auth, **kw):
        with self.assertRaises(AuthenticationRejected) as caught:
            self.authenticate(auth, **kw)
        self.assertEqual(str(caught.exception), "authentication_rejected")
        self.assertTrue(caught.exception.__suppress_context__)

    def test_default_off_and_invalid_configuration_create_no_session(self):
        variants = [dict(enabled=False), dict(enabled=1), dict(enabled=None), dict(max_cache_seconds=True),
                    dict(max_cache_seconds=0), dict(max_cache_seconds=86401), dict(client_secret=""),
                    dict(client_secret="secret\n"), dict(client_secret="s"*4097), dict(client_secret=object()),
                    dict(clock=lambda: float("nan")), dict(clock=lambda: -1), dict(clock=lambda: True),
                    dict(clock=object()), dict(owner_subject="with space"), dict(owner_subject=""),
                    dict(owner_subject="a"*256), dict(client_id="notgoogle.example"),
                    dict(client_id=backend.PRODUCTION_CLIENT_ID)]
        origins = [backend.PRODUCTION_ORIGIN, "http://staging.example.test", ORIGIN+"/", ORIGIN+":443",
                   "https://USER@example.test", "https://staging.example.test?x=y", "https://STAGING.example.test",
                   "https://127.0.0.1", "https://localhost", "https://-stage.example.test",
                   "https://"+"a"*64+".test", "https://staging..test", "https://staging.example.test."]
        variants.extend(dict(origin=origin) for origin in origins)
        with patch.object(backend.requests, "Session") as factory:
            with self.assertRaises(AuthenticationConfigurationError):
                StagingGoogleOwnerAuthenticator(ORIGIN, CLIENT, OWNER, SECRET, 300)
            for options in variants:
                with self.subTest(options=list(options)):
                    with self.assertRaises(AuthenticationConfigurationError) as caught:
                        self.make(**options)
                    self.assertEqual(str(caught.exception), "authentication_configuration_invalid")
            factory.assert_not_called()

    def test_exact_interface_policy_and_no_fixture_dependency(self):
        self.assertEqual(set(inspect.signature(StagingGoogleOwnerAuthenticator).parameters),
                         {"origin", "client_id", "owner_subject", "client_secret", "max_cache_seconds", "enabled", "clock"})
        self.assertEqual(set(inspect.signature(StagingGoogleOwnerAuthenticator.authenticate).parameters),
                         {"self", "code", "flow"})
        import ast
        imports = {alias.name for node in ast.walk(ast.parse(inspect.getsource(backend)))
                   if isinstance(node, ast.Import) for alias in node.names}
        imports |= {node.module for node in ast.walk(ast.parse(inspect.getsource(backend)))
                    if isinstance(node, ast.ImportFrom)}
        self.assertFalse(any("rehearsal" in name or "google_exchange" in name for name in imports))
        auth = self.make()
        self.assertTrue(auth.matches_policy(ORIGIN, CLIENT, OWNER))
        self.assertFalse(auth.matches_policy(ORIGIN, CLIENT, "different-owner"))
        self.assertFalse(auth.matches_policy("https://other.test", CLIENT, OWNER))
        auth.close()
        self.assertFalse(auth.matches_policy(ORIGIN, CLIENT, OWNER))

    def test_real_request_encoding_signature_and_transport_policy(self):
        auth = self.make()
        responses = self.queue()
        claims = self.authenticate(auth)
        self.assertIs(type(claims), VerifiedOwnerClaims)
        self.assertEqual((claims.audience, claims.subject), (CLIENT, OWNER))
        self.assertTrue(claims.signature_verified)
        self.assertEqual(claims.authority, "none")
        self.assertEqual([request.url for _, request, _ in self.sent], [TOKEN_URL, CERTIFICATE_URL])
        first_session, post, _ = self.sent[0]
        self.assertIs(first_session, auth._session)
        data = parse_qs(post.body, strict_parsing=True)
        self.assertEqual(data, {"client_id":[CLIENT], "client_secret":[SECRET], "code":["synthetic-code+/&="],
            "code_verifier":[FLOW.code_verifier], "grant_type":["authorization_code"],
            "redirect_uri":[ORIGIN+"/auth/google/callback"]})
        for session, request, options in self.sent:
            self.assertFalse(session.trust_env)
            self.assertIsNone(session.auth)
            self.assertEqual(session.proxies, {})
            self.assertEqual(session.hooks, {"response": []})
            self.assertFalse(session.cookies)
            self.assertEqual(set(session.adapters), {"https://"})
            self.assertEqual(session.adapters["https://"].max_retries.total, 0)
            self.assertEqual(options["timeout"], (3, 5))
            self.assertIs(options["allow_redirects"], False)
            self.assertIs(options["stream"], True)
            self.assertIs(options["verify"], True)
            self.assertEqual(options["proxies"], {})
            self.assertEqual(request.headers["Accept-Encoding"], "identity")
            self.assertNotIn("Authorization", request.headers)
            self.assertNotIn("Cookie", request.headers)
        self.assertIsNone(self.sent[1][1].body)
        for response in responses:
            self.assertTrue(response.raw.closed)
            self.assertTrue(response.raw.released)
            self.assertTrue(all(0 < n <= 8192 and decode is False for n, decode in response.raw.reads))

    def test_environment_proxy_netrc_and_ca_bundle_never_used(self):
        # Synthetic values only; do not inspect the real process environment.
        with patch("os.environ", {"HTTPS_PROXY":"http://bad.example.test", "REQUESTS_CA_BUNDLE":"synthetic-ca-path"}), \
                patch("requests.sessions.get_netrc_auth", side_effect=AssertionError("credential_read_forbidden")):
            auth = self.make()
            self.queue()
            self.authenticate(auth)
            for _, _, options in self.sent:
                self.assertIs(options["verify"], True)
                self.assertEqual(options["proxies"], {})

    def test_invalid_code_flow_rejected_before_send(self):
        auth = self.make()
        for code in (None, True, b"code", "", "a b", "a\n", "a"*4097, "é"):
            self.reject(auth, code=code)
        for flow in (None, object(), CodeExchangeInputs("x", "V"*64), CodeExchangeInputs("N"*64, "x")):
            self.reject(auth, flow=flow)
        self.assertEqual(self.sent, [])

    def test_response_status_url_history_and_raw_duplicate_headers_rejected(self):
        variants = [self.response(status=302), self.response(status=400), self.response(url="https://evil.example.test"),
                    self.response(headers=[("Content-Type","application/json"),("content-type","application/json")]),
                    self.response(headers=[("Content-Type","application/json"),("Location",TOKEN_URL)]),
                    self.response(headers=[("Content-Type","application/json"),("Set-Cookie","name=value")]),
                    self.response(headers=[("Content-Type","application/json"),("Content-Encoding","gzip")]),
                    self.response(headers=[("Content-Type","application/json"),("Transfer-Encoding","gzip")]),
                    self.response(headers=[("Content-Type","application/json"),("Transfer-Encoding","chunked"),("Content-Length","100")]),
                    self.response(headers=[("Content-Type","application/json"),("X-Test","bad\nvalue")]),
                    self.response(headers=[("Content-Type","application/json"),("X-Test","x"*8192)]),
                    self.response(headers=[("Content-Type","text/plain")]),
                    self.response(headers=[("Content-Type","application/json")]+[(f"X-{i}","a") for i in range(32)])]
        historical = self.response()
        historical.history = [object()]
        variants.append(historical)
        for response in variants:
            with self.subTest(status=response.status_code, url=response.url):
                self.replies.append(response)
                self.reject(self.make())
                self.assertTrue(response.raw.closed)
                self.assertEqual(response.raw.reads, [])

    def test_empty_oversized_truncated_duplicate_and_nonfinite_json(self):
        bodies = [b"", b"x"*65537, b"[]", b"{", b'\xff', b'{"id_token":"a","id_token":"b"}',
                  b'{"value":NaN}', b'{"value":Infinity}', b'{"error":"synthetic-secret-upstream"}',
                  b'{"id_token":"x","token_type":"MAC"}']
        for body in bodies:
            response = self.response(body=body)
            self.replies.append(response)
            self.reject(self.make())
            self.assertTrue(response.raw.closed)
        for value in ("0", "65537", "-1", "1, 1", "abc", "1000000"):
            response = self.response(headers=[("Content-Type","application/json"),("Content-Length",value)])
            self.replies.append(response)
            self.reject(self.make())
            self.assertTrue(response.raw.closed)
            self.assertEqual(response.raw.reads, [])
        mismatch = self.response(headers=[("Content-Type","application/json"),("Content-Length","1")])
        self.replies.append(mismatch)
        self.reject(self.make())
        self.assertTrue(mismatch.raw.closed)

    def test_body_deadline_and_read_error_close_response(self):
        for failure in ("elapsed", "rollback", "exception"):
            auth = self.make()
            response = self.response()
            def hook():
                if failure == "elapsed": self.mono += 11
                elif failure == "rollback": self.mono -= 1
                else: raise requests.Timeout("synthetic-token-should-not-escape")
            response.raw.on_read = hook
            self.replies.append(response)
            self.reject(auth)
            self.assertTrue(response.raw.closed)
            self.mono = 100.0

    def test_transport_exception_is_redacted_and_not_retried(self):
        auth = self.make()
        self.replies.append(requests.ConnectionError("synthetic-secret-upstream"))
        self.reject(auth)
        self.assertEqual(len(self.sent), 1)

    def test_elapsed_request_refuses_result_and_closes_response(self):
        auth = self.make()
        response = self.response()
        self.replies.append(response)
        def delayed_send(session, request, **kwargs):
            self.mono += 21
            return self.send(session, request, **kwargs)
        with patch.object(requests.Session, "send", new=delayed_send):
            self.reject(auth)
        self.assertTrue(response.raw.closed)
        self.assertEqual(response.raw.reads, [])

    def test_certificate_size_key_count_and_untrusted_key_material(self):
        payloads = [b"x"*131073, b"{}", b'{"key":"not-a-certificate"}',
                    json.dumps({str(i):self.cert() for i in range(9)}).encode(),
                    b'{"key":"first","key":"second"}']
        for body in payloads:
            self.queue(cert=False)
            response = self.cert_response()
            response.raw.body = io.BytesIO(body)
            self.replies.append(response)
            auth = self.make()
            self.reject(auth)
            self.assertTrue(response.raw.closed)
            self.assertIsNone(auth._verifier)

    def test_valid_content_length_and_chunked_body(self):
        for header in ("content-length", "transfer-encoding"):
            auth = self.make()
            token_response, certificate_response = self.queue()
            for response in (token_response, certificate_response):
                if header == "content-length":
                    response.raw.headers[header] = str(len(response.raw.body.getvalue()))
                else:
                    response.raw.headers[header] = "chunked"
            self.assertIs(type(self.authenticate(auth)), VerifiedOwnerClaims)

    def test_signature_nonce_owner_issuer_audience_and_times(self):
        variants = [dict(nonce="X"*64), dict(sub="other-owner"), dict(iss="accounts.google.com"),
                    dict(aud="other.apps.googleusercontent.com"), dict(exp=NOW), dict(iat=NOW+1),
                    dict(azp="other.apps.googleusercontent.com"), dict(nbf=NOW+1), dict(exp=True)]
        for claims in variants:
            self.queue(self.token(**claims))
            self.reject(self.make())
        wrong_private = self.wrong_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                    serialization.NoEncryption())
        signer = crypt.RSASigner.from_string(wrong_private, key_id="synthetic-cert")
        self.queue(self.token(signer=signer))
        self.reject(self.make())

    def test_cache_reuse_unknown_kid_no_refresh_and_stale_failure(self):
        auth = self.make()
        self.queue()
        self.authenticate(auth)
        self.queue(cert=False)
        self.authenticate(auth)
        private = self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption())
        signer = crypt.RSASigner.from_string(private, key_id="unknown-key")
        self.queue(self.token(signer=signer), cert=False)
        self.reject(auth)
        self.assertEqual(sum(request.url==CERTIFICATE_URL for _, request, _ in self.sent), 1)
        self.wall += 301
        self.queue(cert=False)
        failed = self.cert_response(status=503)
        self.replies.append(failed)
        self.reject(auth)
        self.assertIsNone(auth._verifier)
        self.assertEqual(auth._valid_until, 0)
        self.assertTrue(failed.raw.closed)
        self.queue()
        self.authenticate(auth)
        self.assertEqual(sum(request.url==CERTIFICATE_URL for _, request, _ in self.sent), 3)

    def test_cache_headers_age_and_certificate_bounds(self):
        cases = [("Cache-Control","no-store, max-age=300"), ("Cache-Control","private, max-age=300"),
                 ("Cache-Control","max-age=300, max-age=300"), ("Cache-Control","max-age=-1"),
                 ("Age","300"), ("Age","-1"), ("Date",formatdate(NOW+1,usegmt=True)),
                 ("Date","invalid")]
        for key, value in cases:
            auth = self.make()
            self.queue(cert=False)
            response = self.cert_response()
            response.raw.headers[key] = value
            self.replies.append(response)
            self.reject(auth)
            self.assertIsNone(auth._verifier)
            self.assertTrue(response.raw.closed)
        for pem in (self.cert(end=NOW), self.cert(begin=NOW+1), "-----BEGIN PUBLIC KEY-----\ninvalid"):
            self.queue(cert=False)
            self.replies.append(self.cert_response(pem=pem))
            self.reject(self.make())
        auth = self.make(max_cache_seconds=20)
        self.queue(cert=False)
        self.replies.append(self.cert_response(pem=self.cert(end=NOW+10), extra=[("Age","5")]))
        self.authenticate(auth)
        self.assertEqual(auth._valid_until, NOW+10)

    def test_explicit_close_and_clock_rollback_permanently_close_session(self):
        for rollback in (False, True):
            auth = self.make()
            session = auth._session
            self.queue()
            self.authenticate(auth)
            with patch.object(session, "close", wraps=session.close) as close:
                if rollback:
                    self.wall -= 1
                    self.reject(auth)
                    self.wall = NOW
                else:
                    auth.close()
                self.reject(auth)
                self.assertEqual(close.call_count, 1)
            self.assertIsNone(auth._session)
            self.assertIsNone(auth._verifier)
            self.assertEqual(auth._client_secret, "")

    def test_cache_response_delay_and_age_reduce_freshness(self):
        auth = self.make()
        self.queue(cert=False)
        response = self.cert_response(extra=[("Age","20")])
        def delay_once():
            self.wall = NOW+10
        response.raw.on_read = delay_once
        self.replies.append(response)
        self.authenticate(auth)
        self.assertEqual(auth._valid_until, NOW+280)

    def test_nested_signature_clock_observation_cannot_roll_back(self):
        auth = self.make()
        self.queue()
        self.authenticate(auth)
        self.queue(cert=False)
        original = backend.StagingIdTokenVerifier.verify
        def observe_then_rollback(verifier, token, *, expected_nonce):
            self.wall = NOW+1
            verifier._now()
            self.wall = NOW
            return original(verifier, token, expected_nonce=expected_nonce)
        with patch.object(backend.StagingIdTokenVerifier, "verify", new=observe_then_rollback):
            self.reject(auth)
        self.wall = NOW+2
        self.reject(auth)
        self.assertIsNone(auth._session)

    def test_nan_and_exception_clock_permanently_close(self):
        for value in (float("nan"), float("inf"), True, -1):
            auth = self.make()
            self.wall = value
            self.reject(auth)
            self.wall = NOW
            self.reject(auth)
            self.assertIsNone(auth._session)

    def test_constructor_session_initialization_failure_closes_session(self):
        original = requests.Session
        session = original()
        with patch.object(session, "mount", side_effect=ValueError("synthetic-secret")), \
                patch.object(session, "close", wraps=session.close) as close, \
                patch.object(backend.requests, "Session", return_value=session):
            with self.assertRaisesRegex(AuthenticationConfigurationError, "^authentication_configuration_invalid$"):
                self.make()
            close.assert_called_once()

    def test_serialized_concurrent_authentication_fetches_keys_once(self):
        auth = self.make()
        self.queue()
        for _ in range(7): self.queue(cert=False)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.authenticate(auth), range(8)))
        self.assertEqual(len(results), 8)
        self.assertTrue(all(type(result) is VerifiedOwnerClaims for result in results))
        self.assertEqual(sum(request.url==CERTIFICATE_URL for _, request, _ in self.sent), 1)


if __name__ == "__main__":
    unittest.main()

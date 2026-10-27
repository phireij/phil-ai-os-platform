"""Inactive Google OIDC identity probe; grants no Mission Control session.

This service must run only behind the dedicated HTTPS Traefik route after a
separate review and deployment approval. It never stores an access/ID token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token

from google_subject_enrollment import GoogleSubjectEnrollment, GoogleSubjectEnrollmentError
from google_oidc_config import CLIENT_ID, ISSUER, REDIRECT_URI, _protected_file
from r3_attestation_handoff import R3AttestationHandoff, R3AttestationHandoffError
from r3_attestation_metadata_writer import R3AttestationMetadataWriter, R3AttestationMetadataWriterError


AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
COOKIE_NAME = "__Host-mc-oauth-probe"
# The OAuth round trip needs to accommodate a human account selection without
# weakening the distinct five-minute lifetime of the issued R3 proof.
FLOW_SECONDS = 900
MAX_FLOWS = 100
ATTEMPT_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,64}\Z")
MAX_TOKEN_RESPONSE_BYTES = 65536
MAX_CERTIFICATE_RESPONSE_BYTES = 131072
CERTIFICATE_URLS = frozenset({
    "https://www.googleapis.com/oauth2/v1/certs",
    "https://www.googleapis.com/oauth2/v3/certs",
})


@dataclass(frozen=True)
class PendingFlow:
    browser_hash: bytes
    nonce: str
    verifier: str
    created_at: float


@dataclass(frozen=True)
class R3MetadataRuntime:
    """Private R3 proof-to-metadata bridge; it has no action capability."""

    handoff: R3AttestationHandoff
    writer: R3AttestationMetadataWriter

    def attest_and_write(self, verified_subject: str) -> None:
        issued = self.handoff.issue_for_verified_subject(
            verified_subject=verified_subject,
            authenticated_at_epoch=int(time.time()),
        )
        self.writer.write(issued.metadata)


class FlowStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._flows: dict[str, PendingFlow] = {}

    def put(self, state: str, flow: PendingFlow) -> bool:
        with self._lock:
            self._expire(time.monotonic())
            if len(self._flows) >= MAX_FLOWS:
                return False
            self._flows[state] = flow
            return True

    def take(self, state: str) -> PendingFlow | None:
        with self._lock:
            flow = self._flows.pop(state, None)
            if flow is None or time.monotonic() - flow.created_at > FLOW_SECONDS:
                return None
            return flow

    def empty(self) -> bool:
        """Report store emptiness for non-sensitive operational diagnostics."""
        with self._lock:
            self._expire(time.monotonic())
            return not self._flows

    def _expire(self, now: float) -> None:
        for key, flow in list(self._flows.items()):
            if now - flow.created_at > FLOW_SECONDS:
                del self._flows[key]


class BoundedGoogleRequest(GoogleRequest):
    def __call__(self, url: str, method: str = "GET", body=None, headers=None, timeout: int = 120, **kwargs):
        if url not in CERTIFICATE_URLS or method != "GET" or body is not None or kwargs:
            raise ValueError("google_certificate_url_invalid")
        response = self.session.get(url, headers=headers, timeout=(3, 5), allow_redirects=False, stream=True)
        try:
            raw = response.raw.read(MAX_CERTIFICATE_RESPONSE_BYTES + 1, decode_content=True)
            if len(raw) > MAX_CERTIFICATE_RESPONSE_BYTES:
                raise ValueError("google_certificate_response_too_large")
            return SimpleNamespace(status=response.status_code, data=raw)
        finally:
            response.close()


def _challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def _cookie_value(raw_cookie: str) -> str:
    try:
        cookie = SimpleCookie()
        cookie.load(raw_cookie)
        return cookie[COOKIE_NAME].value if COOKIE_NAME in cookie else ""
    except Exception:
        return ""


def _single_query_value(query: str, key: str, maximum: int) -> str:
    try:
        values = parse_qs(query, strict_parsing=True, max_num_fields=8).get(key, [])
    except ValueError:
        return ""
    if len(values) != 1 or not values[0] or len(values[0]) > maximum:
        return ""
    return values[0]


def _valid_start_query(query: str) -> bool:
    """Permit only a bounded opaque cache-buster on the existing start route."""
    if not query:
        return True
    try:
        values = parse_qs(query, strict_parsing=True, max_num_fields=1)
    except ValueError:
        return False
    attempt = values.get("attempt", [])
    return len(attempt) == 1 and bool(ATTEMPT_PATTERN.fullmatch(attempt[0]))


def _token_exchange_failure_stage(status_code: int) -> str:
    """Return a fixed, non-sensitive token-exchange failure category."""
    if status_code in (401, 403):
        return "token_exchange_client_rejected"
    if status_code == 429:
        return "token_exchange_rate_limited"
    if 400 <= status_code < 500:
        return "token_exchange_request_rejected"
    if 500 <= status_code < 600:
        return "token_exchange_google_unavailable"
    return "token_exchange_unexpected_status"


def _verified_subject(token: str, nonce: str, session: requests.Session) -> str:
    if len(token) > 16384:
        raise ValueError("id_token_too_large")
    parts = token.split(".")
    if len(parts) != 3 or len(parts[0]) > 2048:
        raise ValueError("id_token_format_invalid")
    header_bytes = base64.urlsafe_b64decode(parts[0] + "=" * (-len(parts[0]) % 4))
    header = json.loads(header_bytes)
    if not isinstance(header, dict) or header.get("alg") != "RS256" or header.get("crit"):
        raise ValueError("id_token_algorithm_invalid")
    if not isinstance(header.get("kid"), str) or len(header["kid"]) > 256:
        raise ValueError("id_token_key_invalid")
    # The Google library validates the signature, audience, issuer, and time.
    claims = google_id_token.verify_oauth2_token(token, BoundedGoogleRequest(session=session), CLIENT_ID)
    if claims.get("iss") != ISSUER:
        raise ValueError("issuer_mismatch")
    if claims.get("azp", CLIENT_ID) != CLIENT_ID:
        raise ValueError("presenter_mismatch")
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise ValueError("nonce_mismatch")
    not_before = claims.get("nbf")
    if not_before is not None and (not isinstance(not_before, (int, float)) or not_before > time.time()):
        raise ValueError("not_before_invalid")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject or len(subject) > 255:
        raise ValueError("subject_invalid")
    return subject


class ProbeHandler(BaseHTTPRequestHandler):
    server_version = "MissionControlGoogleIdentityProbe/0.1"

    def log_message(self, _format: str, *_args: object) -> None:
        # The callback query contains an authorization code; never log it.
        return

    @staticmethod
    def _stage(stage: str) -> None:
        """Emit an allowlisted diagnostic stage without identity or OAuth data."""
        print(f"mission_control_google_probe_stage={stage}", file=sys.stderr, flush=True)

    def _send(self, status: HTTPStatus, body: str, *, location: str | None = None, cookie: str | None = None) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, max-age=0, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Security-Policy", "default-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if location:
            self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        path = urlsplit(self.path)
        if self.headers.get("Host") != "miscon.phireij.cloud":
            self._send(HTTPStatus.BAD_REQUEST, "Invalid host")
            return
        if path.path == "/auth/google/start" and _valid_start_query(path.query):
            self._start()
        elif path.path == "/auth/google/callback":
            self._callback(path.query)
        elif path.path == "/auth/google/healthz" and not path.query:
            self._send(HTTPStatus.OK, "probe_ready;authority_effect=none")
        else:
            self._send(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        self._send(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed")

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST
    do_OPTIONS = do_POST

    def _start(self) -> None:
        state = secrets.token_urlsafe(32)
        browser = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        flow = PendingFlow(hashlib.sha256(browser.encode("ascii")).digest(), nonce, verifier, time.monotonic())
        if not self.server.flows.put(state, flow):  # type: ignore[attr-defined]
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, "Sign-in temporarily unavailable")
            return
        self._stage("flow_created")
        query = urlencode({
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            # Google OIDC requires openid plus email or profile. The probe uses
            # the narrower email alternative only for protocol compliance and
            # discards every identity claim after subject validation.
            "scope": "openid email",
            "state": state,
            "nonce": nonce,
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
        })
        # Google returns through a cross-site OAuth redirect.  The cookie stays
        # host-only, Secure, HTTP-only, and bound to a single 15-minute flow;
        # ``None`` ensures compatible browsers send it on that verified return.
        cookie = f"{COOKIE_NAME}={browser}; Path=/; Secure; HttpOnly; SameSite=None"
        self._send(HTTPStatus.FOUND, "Continue to Google", location=f"{AUTHORIZATION_URL}?{query}", cookie=cookie)

    def _callback(self, query: str) -> None:
        state = _single_query_value(query, "state", 128)
        code = _single_query_value(query, "code", 4096)
        flow = self.server.flows.take(state) if state and code else None  # type: ignore[attr-defined]
        browser = _cookie_value(self.headers.get("Cookie", ""))
        clear_cookie = f"{COOKIE_NAME}=; Path=/; Secure; HttpOnly; SameSite=None; Max-Age=0"
        if not flow:
            flows = self.server.flows  # type: ignore[attr-defined]
            self._stage("rejected_flow_empty" if flows.empty() else "rejected_flow_with_pending")
            self._send(HTTPStatus.UNAUTHORIZED, "Sign-in could not be verified", cookie=clear_cookie)
            return
        # Some managed browsers suppress even a Secure, host-only OAuth return
        # cookie.  The state remains high-entropy, server-held, 15-minute,
        # and single-use; PKCE, nonce, issuer/audience/signature validation,
        # and exact protected-subject matching remain mandatory.  Preserve the
        # cookie binding whenever the browser does supply it, and reject a
        # supplied mismatch rather than silently falling back.
        if browser and not hmac.compare_digest(
            hashlib.sha256(browser.encode("utf-8")).digest(), flow.browser_hash
        ):
            self._stage("rejected_browser_binding")
            self._send(HTTPStatus.UNAUTHORIZED, "Sign-in could not be verified", cookie=clear_cookie)
            return

        stage = "token_exchange"
        try:
            with requests.Session() as session:
                session.trust_env = False
                session.max_redirects = 0
                secret_file = self.server.secret_file  # type: ignore[attr-defined]
                client_secret = secret_file.read_text(encoding="utf-8").strip()
                if not client_secret:
                    raise ValueError("secret_unavailable")
                response = session.post(
                    TOKEN_URL,
                    data={
                        "client_id": CLIENT_ID,
                        "client_secret": client_secret,
                        "code": code,
                        "code_verifier": flow.verifier,
                        "grant_type": "authorization_code",
                        "redirect_uri": REDIRECT_URI,
                    },
                    timeout=(3, 5),
                    allow_redirects=False,
                    stream=True,
                )
                if response.status_code != 200:
                    stage = _token_exchange_failure_stage(response.status_code)
                    response.close()
                    raise ValueError("token_exchange_failed")
                stage = "token_response"
                raw = response.raw.read(MAX_TOKEN_RESPONSE_BYTES + 1, decode_content=True)
                response.close()
                if len(raw) > MAX_TOKEN_RESPONSE_BYTES:
                    raise ValueError("token_response_too_large")
                token_response = json.loads(raw)
                token = token_response.get("id_token") if isinstance(token_response, dict) else None
                if not isinstance(token, str):
                    raise ValueError("id_token_missing")
                stage = "identity_verification"
                verified_subject = _verified_subject(token, flow.nonce, session)
                enrollment = getattr(self.server, "subject_enrollment", None)
                if enrollment is not None:
                    stage = "subject_enrollment"
                    enrollment.enroll(verified_subject)
                r3_runtime = getattr(self.server, "r3_metadata_runtime", None)
                if r3_runtime is not None:
                    stage = "metadata_write"
                    r3_runtime.attest_and_write(verified_subject)
        except Exception:
            # Neither the exception nor the authorization code may reach a log.
            self._stage(f"failed_{stage}")
            self._send(HTTPStatus.BAD_GATEWAY, "Google sign-in could not be completed", cookie=clear_cookie)
            return

        enrolled = getattr(self.server, "subject_enrollment", None) is not None
        r3_written = getattr(self.server, "r3_metadata_runtime", None) is not None
        body = (
            "<!doctype html><html><head><title>CEO identity probe</title></head><body>"
            "<h1>Google identity verified</h1><p>No Mission Control session was created.</p>"
            + ("<p>A protected subject digest was enrolled for later exact matching.</p>" if enrolled else "<p>Identity details are not displayed or retained by this probe.</p>")
            + ("<p>R3 reauthentication metadata was recorded with no action authority.</p>" if r3_written else "")
            + "</body></html>"
        )
        self._stage("verified")
        self._send(HTTPStatus.OK, body, cookie=clear_cookie)


def main() -> None:
    if os.environ.get("MISSION_CONTROL_GOOGLE_PROBE_ENABLED") != "true":
        raise SystemExit("google_identity_probe_inactive")
    if os.environ.get("MISSION_CONTROL_GOOGLE_CLIENT_ID") != CLIENT_ID:
        raise SystemExit("google_identity_probe_client_id_invalid")
    secret_file = _protected_file("MISSION_CONTROL_GOOGLE_CLIENT_SECRET_FILE")
    server = ThreadingHTTPServer(("0.0.0.0", 8092), ProbeHandler)
    server.flows = FlowStore()  # type: ignore[attr-defined]
    server.secret_file = secret_file  # type: ignore[attr-defined]
    if os.environ.get("MISSION_CONTROL_GOOGLE_SUBJECT_ENROLLMENT_ENABLED") == "true":
        try:
            server.subject_enrollment = GoogleSubjectEnrollment.from_environment()  # type: ignore[attr-defined]
        except GoogleSubjectEnrollmentError as error:
            raise SystemExit(str(error)) from error
    if os.environ.get("MISSION_CONTROL_R3_ATTESTATION_RUNTIME_ENABLED") == "true":
        try:
            server.r3_metadata_runtime = R3MetadataRuntime(  # type: ignore[attr-defined]
                handoff=R3AttestationHandoff.from_environment(),
                writer=R3AttestationMetadataWriter.from_environment(),
            )
        except (R3AttestationHandoffError, R3AttestationMetadataWriterError, ValueError) as error:
            raise SystemExit(str(error)) from error
    server.serve_forever()


if __name__ == "__main__":
    main()

"""Inactive Google ID-token verification primitive with no network adapter.

Uses the pinned google-auth library for RSA signature, audience and time checks,
then enforces stricter staging issuer/owner/nonce/schema/expiry requirements.
Trust snapshots MUST come from a separately reviewed server-side Google key
retrieval/cache path. This module does not establish that provenance. Local tests
use synthetic keys only. Returned claims have no session/execution authority.
No file/environment credential loader, code exchange, listener or production
identity import is included. No token-supplied URL or key is ever trusted.
"""

from __future__ import annotations

import base64
import hmac
import json
import math
import re
import threading
import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Mapping

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from google.auth import jwt as google_jwt


ISSUER = "https://accounts.google.com"
PRODUCTION_CLIENT_ID = "531519060424-c2n6uclfuko18tubr9ejs9o2fhf8s4c1.apps.googleusercontent.com"
_CLIENT = re.compile(r"[A-Za-z0-9_-]{1,200}\.apps\.googleusercontent\.com", re.ASCII)
_SUBJECT = re.compile(r"[A-Za-z0-9_-]{1,255}", re.ASCII)
_NONCE = re.compile(r"[A-Za-z0-9_-]{64}", re.ASCII)
_KID = re.compile(r"[A-Za-z0-9_-]{1,128}", re.ASCII)
_B64 = re.compile(r"[A-Za-z0-9_-]+", re.ASCII)


class TokenRejected(ValueError):
    """A constant non-secret error; never expose underlying library exceptions."""


class VerifierConfigurationError(ValueError):
    """A constant non-secret configuration error."""


def _reject() -> None:
    raise TokenRejected("id_token_rejected")


def _bounded_integer(value: object) -> bool:
    return type(value) is int and 0 <= value <= 2**53


def _pairs(values: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in values:
        if key in result:
            _reject()
        result[key] = value
    return result


def _constant(_value: str):
    _reject()


def _segment(segment: str) -> bytes:
    if not _B64.fullmatch(segment):
        _reject()
    raw = base64.b64decode(segment + "=" * (-len(segment) % 4), altchars=b"-_", validate=True)
    if base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != segment:
        _reject()
    return raw


def _object(segment: str) -> dict:
    value = json.loads(_segment(segment).decode("utf-8"), object_pairs_hook=_pairs,
                       parse_constant=_constant)
    if type(value) is not dict:
        _reject()
    return value


@dataclass(frozen=True)
class VerifiedOwnerClaims:
    """Verified against supplied trust roots, NOT a principal or session grant."""

    issuer: str
    audience: str = field(repr=False)
    subject: str = field(repr=False)
    issued_at: int
    expires_at: int
    signature_verified: bool = True
    owner_matches: bool = True
    authority: str = "none"
    trust_provenance: str = "external_server_responsibility"


class StagingIdTokenVerifier:
    """Immutable snapshot of server-selected identity policy and public keys.

    Public PEM keys/certificates are accepted only at trusted construction time,
    never from an incoming token/request. Snapshot expiry is required and cannot
    be extended after creation. Unknown kid/stale snapshots fail without refresh.
    This class has no fetcher. Code exchange and browser-bound one-use state/PKCE
    remain outside it; checking a nonce here is not itself replay prevention.
    """

    def __init__(self, *, audience: str, owner_subject: str,
                 trusted_pems: Mapping[str, bytes], keys_valid_until: int,
                 enabled: bool = False, clock: Callable[[], float] = time.time) -> None:
        try:
            if enabled is not True or type(audience) is not str or not _CLIENT.fullmatch(audience):
                raise ValueError
            if audience == PRODUCTION_CLIENT_ID or type(owner_subject) is not str or not _SUBJECT.fullmatch(owner_subject):
                raise ValueError
            if not _bounded_integer(keys_valid_until) or not isinstance(trusted_pems, Mapping):
                raise ValueError
            if not 1 <= len(trusted_pems) <= 8:
                raise ValueError
            snapshot: dict[str, bytes] = {}
            valid_until = keys_valid_until
            valid_from = 0.0
            for kid, pem in trusted_pems.items():
                if type(kid) is not str or not _KID.fullmatch(kid) or type(pem) is not bytes or not 1 <= len(pem) <= 16384:
                    raise ValueError
                if pem.startswith(b"-----BEGIN CERTIFICATE-----"):
                    certificate = x509.load_pem_x509_certificate(pem)
                    key = certificate.public_key()
                    valid_until = min(valid_until, int(certificate.not_valid_after_utc.timestamp()))
                    valid_from = max(valid_from, certificate.not_valid_before_utc.timestamp())
                    if valid_from > clock():
                        raise ValueError
                else:
                    key = serialization.load_pem_public_key(pem)
                if not isinstance(key, RSAPublicKey) or not 2048 <= key.key_size <= 4096:
                    raise ValueError
                snapshot[kid] = key.public_bytes(serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo)
            now = clock()
            if type(now) not in (float, int) or not math.isfinite(now) or now < valid_from or now >= valid_until:
                raise ValueError
            self._audience = audience
            self._owner = owner_subject
            self._keys = MappingProxyType(snapshot)
            self._keys_valid_until = valid_until
            self._clock = clock
            self._time_lock = threading.Lock()
            self._last_now = now
            self._closed = False
        except Exception:
            raise VerifierConfigurationError("verifier_configuration_invalid") from None

    def _now(self) -> float:
        # Once stale or clock-invalid, this snapshot cannot become usable again
        # after a wall-clock rollback. A new trusted snapshot is required.
        with self._time_lock:
            if self._closed:
                _reject()
            try:
                now = self._clock()
                valid = (type(now) in (float, int) and math.isfinite(now)
                         and self._last_now <= now < self._keys_valid_until)
            except Exception:
                valid = False
            if not valid:
                self._closed = True
                _reject()
            self._last_now = now
            return now

    def verify(self, token: object, *, expected_nonce: str) -> VerifiedOwnerClaims:
        """Return only after maintained-library signature and exact owner checks.

        The expected nonce must be from the server's consumed browser-bound flow,
        not a value supplied alongside a token by an untrusted request caller.
        """
        try:
            now = self._now()
            if type(token) is not str or not 1 <= len(token) <= 16384 or token.count(".") != 2:
                _reject()
            if type(expected_nonce) is not str or not _NONCE.fullmatch(expected_nonce):
                _reject()
            encoded_header, encoded_payload, encoded_signature = token.split(".")
            if len(encoded_header) > 2048 or len(encoded_signature) > 1024:
                _reject()
            header, payload = _object(encoded_header), _object(encoded_payload)
            _segment(encoded_signature)
            if set(header) - {"alg", "kid", "typ"} or header.get("alg") != "RS256":
                _reject()
            if "typ" in header and header["typ"] != "JWT":
                _reject()
            kid = header.get("kid")
            if type(kid) is not str or not _KID.fullmatch(kid) or kid not in self._keys:
                _reject()
            required = {"iss", "aud", "sub", "nonce", "iat", "exp"}
            if not required <= set(payload):
                _reject()
            if any(type(payload[key]) is not str for key in ("iss", "aud", "sub", "nonce")):
                _reject()
            if not _SUBJECT.fullmatch(payload["sub"]) or not _NONCE.fullmatch(payload["nonce"]):
                _reject()
            if any(not _bounded_integer(payload[key]) for key in ("iat", "exp")):
                _reject()
            if "nbf" in payload and not _bounded_integer(payload["nbf"]):
                _reject()
            if "azp" in payload and (type(payload["azp"]) is not str or payload["azp"] != self._audience):
                _reject()
            if not payload["iat"] <= now < payload["exp"] or payload["exp"] <= payload["iat"] or payload.get("nbf", 0) > now:
                _reject()
            # No unverified claim is ever returned. Explicit audience, signature
            # verification and zero skew cannot be disabled by the caller.
            verified = google_jwt.decode(token, certs={kid: self._keys[kid]},
                                         verify=True, audience=self._audience,
                                         clock_skew_in_seconds=0)
            if verified != payload or payload["iss"] != ISSUER or payload["aud"] != self._audience:
                _reject()
            if not hmac.compare_digest(payload["sub"], self._owner) or not hmac.compare_digest(payload["nonce"], expected_nonce):
                _reject()
            # Account for time passing while signature verification runs. The
            # pinned helper accepts exp==now; the OIDC wrapper rejects it.
            now = self._now()
            if not payload["iat"] <= now < payload["exp"] or payload.get("nbf", 0) > now:
                _reject()
            return VerifiedOwnerClaims(ISSUER, self._audience, self._owner,
                                       payload["iat"], payload["exp"])
        except Exception:
            raise TokenRejected("id_token_rejected") from None

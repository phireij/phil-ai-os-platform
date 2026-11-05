"""Opt-in raw-request boundary for the inactive Ruby staging worker.

Enforces request-target identity before WSGI unquoting and requires the pinned
parser's underscore refusal with no forwarding-header exceptions. It never
selects proxy peers, rewrites scheme/Host, or starts a server. Only a validated
single Connection close/keep-alive token is removed before WSGI conversion.
"""
from __future__ import annotations

import os

from gunicorn import util
from gunicorn.config import PostRequest, PreRequest
from gunicorn.http.errors import ConfigurationProblem, InvalidHeader, InvalidRequestLine
from gunicorn.http.message import Request

from ruby_staging_gunicorn_worker import StagingSyncWorker


class StagingBoundaryConfigurationError(ValueError):
    pass


_PERMISSIVE = (
    "permit_obsolete_folding", "strip_header_spaces", "casefold_http_method",
    "permit_unconventional_http_method", "permit_unconventional_http_version",
)


def _parser_policy_valid(cfg):
    try:
        script_name = cfg.env.get("SCRIPT_NAME", "")
    except Exception:
        return False
    return (
        getattr(cfg, "http_parser", None) == "python"
        and getattr(cfg, "protocol", None) == "http"
        and getattr(cfg, "http_protocols", None) == ["h1"]
        and getattr(cfg, "header_map", None) == "refuse"
        and getattr(cfg, "forwarder_headers", None) == []
        and getattr(cfg, "pre_request", None) is PreRequest.pre_request
        and getattr(cfg, "post_request", None) is PostRequest.post_request
        and script_name == "" and os.environ.get("SCRIPT_NAME", "") == ""
        and all(getattr(cfg, name, None) is False for name in _PERMISSIVE)
    )


def _target_is_canonical(req):
    if type(req) is not Request or type(req.uri) is not str:
        return False
    raw = req.uri
    # These text/length rules mirror the staging app's existing path/query
    # envelope. No decoding or normalization is performed here.
    if (not raw.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in raw)
            or "#" in raw):
        return False
    path, _, query = raw.partition("?")
    if (not path.startswith("/") or path.startswith("//") or len(path) > 256
            or len(query) > 8192 or any(c in path for c in "%\\")
            or "//" in path or any(part in {".", ".."} for part in path.split("/"))):
        return False
    # Ensure upstream URL splitting did not discard, move, or change any bytes.
    # Valid percent escapes and reserved characters in OAuth query VALUES remain
    # untouched; the app's existing strict query parser still decides validity.
    return (type(req.path) is str and req.path == path
            and type(req.query) is str and req.query == query
            and req.fragment == "")


_FORBIDDEN_TRANSPORT_HEADERS = frozenset({
    "EXPECT", "TRANSFER-ENCODING", "TE", "TRAILER", "UPGRADE",
})


def _validated_headers(req):
    """Validate the intact parsed list before upstream can emit 100 Continue.

    Never collapse duplicate evidence or strip nominated client fields. The one
    compatibility exception cannot nominate any field and retains forced-close
    responses. Framing content lengths remain governed by the pinned parser and
    the application's existing method/body bounds.
    """
    if type(req.headers) is not list or req._expected_100_continue is not False:
        raise InvalidHeader("staging_request_headers_invalid")
    connection_seen = False
    headers = []
    for item in req.headers:
        if (type(item) is not tuple or len(item) != 2
                or type(item[0]) is not str or type(item[1]) is not str):
            raise InvalidHeader("staging_request_headers_invalid")
        name, value = item
        if name in _FORBIDDEN_TRANSPORT_HEADERS:
            raise InvalidHeader("staging_request_headers_invalid")
        if name == "CONNECTION":
            if (connection_seen or not value.isascii()
                    or value.lower() not in {"close", "keep-alive"}):
                raise InvalidHeader("staging_request_headers_invalid")
            connection_seen = True
        else:
            headers.append(item)
    return headers


class StagingCanonicalWorker(StagingSyncWorker):
    """Reviewed Python HTTP/1 parser policy plus pre-WSGI target validation."""

    def __init__(self, age, ppid, sockets, app, timeout, cfg, log):
        if not _parser_policy_valid(cfg):
            raise StagingBoundaryConfigurationError("staging_parser_configuration_invalid")
        super().__init__(age, ppid, sockets, app, timeout, cfg, log)

    def handle(self, listener, client, addr):
        # Recheck before parsing so an in-process configuration change cannot
        # silently turn refusal back into dropping/normalization. Do not mutate
        # configuration or guess a proxy trust policy to recover.
        if not _parser_policy_valid(self.cfg):
            self.alive = False
            try:
                self.log.error("staging_parser_configuration_invalid")
            finally:
                # No handshake has happened yet: never emit plaintext HTTP onto
                # an unwrapped TLS client, and do not drain unparsed bytes.
                util.close(client)
            return
        return super().handle(listener, client, addr)

    def handle_request(self, listener, req, client, addr):
        if not _parser_policy_valid(self.cfg):
            self.alive = False
            raise ConfigurationProblem("staging_parser_configuration_invalid")
        if not _target_is_canonical(req):
            # The safe inherited error handler never reflects this or raw input.
            raise InvalidRequestLine("staging_request_target_invalid")
        headers = _validated_headers(req)
        # Commit the only permitted removal after the entire list passed. All
        # other headers, values, order and duplicate evidence are preserved.
        req.headers = headers
        return super().handle_request(listener, req, client, addr)

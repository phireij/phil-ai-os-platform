"""Opt-in staging-only generic HTTP error responses for pinned Gunicorn.

No server is started or configuration selected by import. The original parser,
request handling, normal responses, abort method and worker lifecycle are inherited.
Canonical raw-target/header policy and trusted ingress remain separate gates.
"""
from __future__ import annotations

from datetime import timedelta
from ssl import SSLError
from types import SimpleNamespace

import gunicorn
from gunicorn import util
from gunicorn.http.errors import (
    ChunkMissingTerminator, ConfigurationProblem, ExpectationFailed,
    ForbiddenProxyRequest, InvalidChunkExtension, InvalidChunkSize,
    InvalidH2CPreface, InvalidHeader, InvalidHeaderName, InvalidHTTPVersion,
    InvalidProxyLine, InvalidRequestLine, InvalidRequestMethod,
    InvalidSchemeHeaders, LimitRequestHeaders, LimitRequestLine, ObsoleteFolding,
    UnsupportedTransferCoding,
)
from gunicorn.http.message import Request
from gunicorn.workers.sync import SyncWorker

from ruby_staging_gunicorn_logging import StagingGunicornLogger


class StagingWorkerConfigurationError(ValueError):
    pass


_REASONS = {
    400: "Bad Request", 403: "Forbidden", 417: "Expectation Failed",
    431: "Request Header Fields Too Large", 500: "Internal Server Error",
    501: "Not Implemented",
}
_BODY = (b'{"error":"request_failed","authority":"none",'
         b'"execution_authorized":false,"mutation_authorized":false}')


def _response(status, *, head=False, unidentified=False):
    # status comes only from the internal finite map. No request/exception data
    # enters the status line, headers, or body, including malformed input.
    body = b"" if unidentified else _BODY
    headers = (
        f"HTTP/1.1 {status} {_REASONS[status]}\r\n"
        "Connection: close\r\n"
        "Content-Type: application/json; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Cache-Control: no-store\r\n"
        "Pragma: no-cache\r\n"
        "Referrer-Policy: no-referrer\r\n"
        "X-Content-Type-Options: nosniff\r\n"
        "Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'\r\n"
        "X-Frame-Options: DENY\r\n\r\n"
    ).encode("ascii")
    return headers if head else headers + body


def _status(exc):
    if isinstance(exc, (ForbiddenProxyRequest, SSLError)):
        return 403
    if isinstance(exc, ExpectationFailed):
        return 417
    if isinstance(exc, LimitRequestHeaders):
        return 431
    if isinstance(exc, UnsupportedTransferCoding):
        return 501
    if isinstance(exc, ConfigurationProblem):
        return 500
    if isinstance(exc, (InvalidRequestLine, InvalidRequestMethod, InvalidHTTPVersion,
                        InvalidHeader, InvalidHeaderName, LimitRequestLine,
                        InvalidProxyLine, InvalidSchemeHeaders, ObsoleteFolding,
                        InvalidH2CPreface, InvalidChunkSize, ChunkMissingTerminator,
                        InvalidChunkExtension)):
        return 400
    return 500


class StagingSyncWorker(SyncWorker):
    """Generic errors only, with the separately reviewed opt-in logger required."""

    def __init__(self, age, ppid, sockets, app, timeout, cfg, log):
        if gunicorn.__version__ != "26.2.2" or type(log) is not StagingGunicornLogger:
            raise StagingWorkerConfigurationError("staging_worker_configuration_invalid")
        super().__init__(age, ppid, sockets, app, timeout, cfg, log)

    def handle_error(self, req, client, addr, exc):
        # Unusual control-flow BaseExceptions may occur after a partial response.
        # Do not append a response or swallow their shutdown intent. SystemExit
        # follows the existing pinned handler contract: before headers it reaches
        # here; after headers handle_request closes and raises StopIteration.
        if not isinstance(exc, (Exception, SystemExit)):
            raise exc

        status = _status(exc)
        if status >= 500:
            self.log.error("Error handling request")
        else:
            self.log.warning("staging_request_rejected")
        self.log.access(SimpleNamespace(status=status), None, {}, timedelta(0))
        # Early parser errors occur before handle assigns req, even for HEAD.
        # Never reparse raw text or guess the method: no complete parsed request
        # means an empty response representation for every method.
        known = type(req) is Request
        head = known and type(req.method) is str and req.method == "HEAD"
        response = _response(status, head=head, unidentified=not known)
        try:
            # Preserve upstream's nonblocking error-write behavior. One bounded
            # payload, no retry on partial/write failure. This is not a hosted
            # wall-clock deadline or proof about kernel/close scheduling.
            util.write_nonblock(client, response)
        except Exception:
            self.log.debug("Failed to send error message.")

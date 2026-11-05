"""Opt-in staging-only generic HTTP error responses for pinned Gunicorn.

No server is started or configuration selected by import. The original parser,
request handling, normal responses, abort method and worker lifecycle are retained.
Canonical raw-target/header policy and trusted ingress remain separate gates.
TLS wrapping failures close without HTTP serialization or draining raw input.
"""
from __future__ import annotations

from datetime import timedelta
from ssl import SSLError, SSLSocket
from types import SimpleNamespace

import gunicorn
from gunicorn import http, sock, util
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


def _tls_transport(client):
    # A callback returning an arbitrary object is not a TLS transport. Reject
    # subclasses that can replace the standard socket's encryption semantics.
    return type(client) is SSLSocket


def _tls_ready(client):
    try:
        return _tls_transport(client) and client.version() in {"TLSv1.2", "TLSv1.3"}
    except Exception:
        return False


def _close_untrusted_transport(client):
    # A failed callback can return None or a foreign object. Best-effort close
    # must neither read it nor prevent the original raw socket being closed.
    try:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    except Exception:
        pass


class StagingSyncWorker(SyncWorker):
    """Generic errors only, with the separately reviewed opt-in logger required."""

    def __init__(self, age, ppid, sockets, app, timeout, cfg, log):
        if gunicorn.__version__ != "26.2.2" or type(log) is not StagingGunicornLogger:
            raise StagingWorkerConfigurationError("staging_worker_configuration_invalid")
        super().__init__(age, ppid, sockets, app, timeout, cfg, log)

    def handle(self, listener, client, addr):
        """Pinned sync request flow with an explicit pre-TLS error boundary.

        No context, certificate, TLS policy or timeout is selected here. Wrapping
        remains upstream; TLS failures never use its generic HTTP error path.
        Successful parser/application responses retain the pinned request handler.
        """
        raw_client, req, wrapped_client = client, None, None
        tls, wrapped, drift, transport_known = False, False, False, False
        try:
            tls = bool(self.cfg.is_ssl)
            transport_known = True
            if tls:
                wrapped_client = sock.ssl_wrap_socket(client, self.cfg)
                if not _tls_transport(wrapped_client):
                    raise ConfigurationProblem("staging_tls_transport_invalid")
                client, wrapped = wrapped_client, True
                # An exact SSLSocket can fall back to raw socket operations after
                # unwrap. It must already have completed reviewed-version TLS.
                # Do not initiate a lazy handshake or invent its deadline here.
                if not _tls_ready(client):
                    raise ConfigurationProblem("staging_tls_transport_unready")
            # A callback must not change the parser's transport-mode declaration.
            if bool(self.cfg.is_ssl) != tls:
                drift = True
                raise ConfigurationProblem("staging_transport_configuration_invalid")
            parser = http.get_parser(self.cfg, client, addr)
            req = next(parser)
            if tls and not _tls_ready(client):
                raise ConfigurationProblem("staging_tls_transport_unready")
            self.handle_request(listener, req, client, addr)
        except (http.errors.NoMoreData, StopIteration):
            self.log.debug("staging_connection_closed")
        except SSLError:
            # Even after a prior handshake, a TLS failure is not an HTTP error.
            self.log.warning("staging_tls_transport_failed")
        except OSError:
            self.log.debug("staging_transport_closed")
        except BaseException as exc:
            if not isinstance(exc, (Exception, SystemExit)):
                raise
            if not transport_known or drift or (tls and (not wrapped or not _tls_ready(client))):
                self.log.warning("staging_tls_transport_failed")
            else:
                self.handle_error(req, client, addr, exc)
        finally:
            # Never drain an unwrapped or unestablished TLS stream. Do not invent
            # a handshake deadline here. Upstream graceful close remains only for
            # an established transport; its limits are not hosted acceptance.
            if not transport_known or drift or (tls and (not wrapped or not _tls_ready(client))):
                try:
                    if wrapped_client is not None and wrapped_client is not raw_client:
                        _close_untrusted_transport(wrapped_client)
                finally:
                    _close_untrusted_transport(raw_client)
            else:
                util.close_graceful(client)

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

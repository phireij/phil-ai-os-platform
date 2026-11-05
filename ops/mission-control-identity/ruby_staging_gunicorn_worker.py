"""Opt-in staging-only generic HTTP error responses for pinned Gunicorn.

No server is started or configuration selected by import. The original parser,
request handling, normal responses, abort method and worker lifecycle are retained.
Canonical raw-target/header policy and trusted ingress remain separate gates.
TLS wrapping/protocol failures close without HTTP serialization or draining input.
This staging profile requires explicit HTTP/1.1 ALPN, even though absent ALPN
can be legal TLS. It is not a general-purpose TLS compatibility policy.
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
        if not _tls_transport(client) or client.version() not in {"TLSv1.2", "TLSv1.3"}:
            return False
        protocol = client.selected_alpn_protocol()
        return type(protocol) is str and protocol == "http/1.1"
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

        No context, certificate or timeout is selected here. Wrapping remains
        upstream; TLS must meet this staging profile before HTTP parsing.
        Successful parser/application responses retain the pinned request handler.
        """
        raw_client, req, wrapped_client = client, None, None
        tls, wrapped, drift, transport_known = False, False, False, False
        tls_rejected = False

        def tls_usable():
            nonlocal tls_rejected
            if tls_rejected or not wrapped:
                return False
            # Refusal is terminal, including an interrupted readiness probe.
            # Later observations cannot turn a rejected stream into HTTP/drain.
            tls_rejected = True
            tls_rejected = not _tls_ready(client)
            return not tls_rejected

        try:
            tls = bool(self.cfg.is_ssl)
            transport_known = True
            if tls:
                wrapped_client = sock.ssl_wrap_socket(client, self.cfg)
                if not _tls_transport(wrapped_client):
                    raise ConfigurationProblem("staging_tls_transport_invalid")
                client, wrapped = wrapped_client, True
                # An exact SSLSocket can fall back to raw socket operations after
                # unwrap. It must have completed reviewed-version TLS and
                # explicitly negotiated HTTP/1.1 before this parser can run.
                # Do not initiate a lazy handshake or invent its deadline here.
                if not tls_usable():
                    raise ConfigurationProblem("staging_tls_transport_unready")
            # A callback must not change the parser's transport-mode declaration.
            if bool(self.cfg.is_ssl) != tls:
                drift = True
                raise ConfigurationProblem("staging_transport_configuration_invalid")
            parser = http.get_parser(self.cfg, client, addr)
            req = next(parser)
            if tls and not tls_usable():
                raise ConfigurationProblem("staging_tls_transport_unready")
            self.handle_request(listener, req, client, addr)
        except (http.errors.NoMoreData, StopIteration):
            self.log.debug("staging_connection_closed")
        except SSLError:
            # Even after a prior handshake, a TLS failure is not an HTTP error.
            tls_rejected = True
            self.log.warning("staging_tls_transport_failed")
        except OSError:
            self.log.debug("staging_transport_closed")
        except BaseException as exc:
            if not isinstance(exc, (Exception, SystemExit)):
                raise
            if not transport_known or drift or (tls and not tls_usable()):
                self.log.warning("staging_tls_transport_failed")
            else:
                self.handle_error(req, client, addr, exc)
        finally:
            # Never drain an unwrapped, unestablished or rejected TLS stream.
            # Cleanup still closes if the final probe is interrupted. Do not invent
            # a handshake deadline here. Upstream graceful close remains only for
            # an established transport; its limits are not hosted acceptance.
            graceful = False
            try:
                graceful = transport_known and not drift and (not tls or tls_usable())
            finally:
                if graceful:
                    util.close_graceful(client)
                else:
                    try:
                        if wrapped_client is not None and wrapped_client is not raw_client:
                            _close_untrusted_transport(wrapped_client)
                    finally:
                        _close_untrusted_transport(raw_client)

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

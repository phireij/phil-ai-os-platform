"""Opt-in, staging-only Gunicorn 26.2.2 diagnostic logger.

Importing this module does not select it or start anything. A future reviewed
server configuration must explicitly select this class. No application, request,
HTTP handler, abort handler, response body, or deployment setting is changed.

Request URIs, query values, headers, exception messages and tracebacks never enter
records produced by this Logger API. Diagnostics intentionally retain only fixed
event names, severity, normal logging timestamp/PID, and validated response status.
This does not sanitize arbitrary application stdout/stderr or other logger APIs.
"""
from __future__ import annotations

import logging

import gunicorn
from gunicorn.glogging import Logger


class StagingLoggingConfigurationError(ValueError):
    pass


_EVENTS = {
    logging.DEBUG: "staging_server_debug",
    logging.INFO: "staging_server_info",
    logging.WARNING: "staging_server_warning",
    logging.ERROR: "staging_server_error",
    logging.CRITICAL: "staging_server_critical",
}
_TEMPLATES = {
    "Error handling request %s %s": "staging_request_error",
    "Error handling request %s": "staging_request_error",
    "Error handling request (no URI read)": "staging_request_error",
    "Error handling request": "staging_request_error",
    "Ignored premature client disconnection. %s": "staging_request_incomplete",
    "Closing connection. %s": "staging_connection_closed",
    "WORKER TIMEOUT (pid:%s)": "staging_worker_timeout",
    "Booting worker with pid: %s": "staging_worker_started",
    "Worker exiting (pid: %s)": "staging_worker_exiting",
    "%s %s": "staging_request_started",
}


class StagingGunicornLogger(Logger):
    """Fixed-field Logger implementation; not a server entrypoint or activation."""

    def setup(self, cfg):
        # Fail before upstream setup can open a configured file/socket or load
        # arbitrary formatter/handler code. Output streams remain operator-owned.
        if (gunicorn.__version__ != "26.2.2" or cfg.capture_output or cfg.syslog
                or cfg.logconfig or cfg.logconfig_json or cfg.logconfig_dict
                or cfg.errorlog != "-" or cfg.accesslog not in (None, "-")):
            raise StagingLoggingConfigurationError("staging_logging_configuration_invalid")
        super().setup(cfg)

    def _event(self, level, msg, *, exception=False):
        fallback = "staging_server_exception" if exception else _EVENTS[level]
        event = _TEMPLATES.get(msg, fallback) if type(msg) is str else fallback
        self.error_log.log(level, event)

    def critical(self, msg, *args, **kwargs):
        self._event(logging.CRITICAL, msg)

    def error(self, msg, *args, **kwargs):
        self._event(logging.ERROR, msg)

    def warning(self, msg, *args, **kwargs):
        self._event(logging.WARNING, msg)

    def info(self, msg, *args, **kwargs):
        self._event(logging.INFO, msg)

    def debug(self, msg, *args, **kwargs):
        self._event(logging.DEBUG, msg)

    def exception(self, msg, *args, **kwargs):
        # Do not delegate to Logger.exception: current exception text, traceback
        # source lines and chained exceptions may contain callback query values.
        self._event(logging.ERROR, msg, exception=True)

    def log(self, lvl, msg, *args, **kwargs):
        if type(lvl) is str:
            level = self.LOG_LEVELS.get(lvl.lower(), logging.INFO)
        elif type(lvl) is int and lvl in _EVENTS:
            level = lvl
        else:
            level = logging.INFO
        self._event(level, msg)

    @staticmethod
    def _status(resp):
        value = getattr(resp, "status", None)
        if type(value) is int and 100 <= value <= 599:
            return value
        if type(value) is str:
            part = value.split(" ", 1)[0]
            if len(part) == 3 and part.isascii() and part.isdigit() and 100 <= int(part) <= 599:
                return int(part)
        return "unknown"

    def atoms(self, resp, req, environ, request_time):
        # Never construct the base atoms, which include raw URI, cookies,
        # arbitrary headers, response cookies, user identity and environment.
        return {"s": self._status(resp)}

    def access(self, resp, req, environ, request_time):
        if self.access_log_enabled:
            # Deliberately ignore access_log_format, which can otherwise restore
            # raw request fields. Only a validated status code is rendered.
            self.access_log.info("staging_http_response status=%s", self._status(resp))

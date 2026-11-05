"""Opt-in, staging-only one-worker controller for pinned Gunicorn 26.2.2.

No launcher or default configuration selects this class. This bounds workers
created by ONE trusted master; it is not a host/container singleton lock. A
future launcher must also construct the app after fork, own its cleanup, and
verify the old service's entire process group is gone before starting another.
"""
from __future__ import annotations

import errno
import os
import signal

import gunicorn
from gunicorn.arbiter import Arbiter
from gunicorn.config import (Config, OnStarting, OnReload, WhenReady, Prefork,
    Postfork, PostWorkerInit, WorkerInt, WorkerAbort, PreExec, ChildExit,
    WorkerExit, NumWorkersChanged, OnExit)
from gunicorn.errors import HaltServer

from ruby_staging_gunicorn_boundary import _parser_policy_valid
from ruby_staging_gunicorn_application import StagingOwnedWorker, StagingPostForkApplication
from ruby_staging_gunicorn_logging import StagingGunicornLogger


class StagingArbiterConfigurationError(ValueError):
    pass


_HOOKS = {
    "on_starting": OnStarting.on_starting, "on_reload": OnReload.on_reload,
    "when_ready": WhenReady.when_ready, "pre_fork": Prefork.pre_fork,
    "post_fork": Postfork.post_fork, "post_worker_init": PostWorkerInit.post_worker_init,
    "worker_int": WorkerInt.worker_int, "worker_abort": WorkerAbort.worker_abort,
    "pre_exec": PreExec.pre_exec, "child_exit": ChildExit.child_exit,
    "worker_exit": WorkerExit.worker_exit,
    "nworkers_changed": NumWorkersChanged.nworkers_changed, "on_exit": OnExit.on_exit,
}
_INHERITED_MASTER_ENV = {
    "GUNICORN_PID", "GUNICORN_FD", "LISTEN_PID", "LISTEN_FDS",
    "LISTEN_FDNAMES", "NOTIFY_SOCKET",
}


def _policy_valid(cfg):
    try:
        return (
            gunicorn.__version__ == "26.2.2" and type(cfg) is Config
            and type(cfg.workers) is int and cfg.workers == 1
            and type(cfg.threads) is int and cfg.threads == 1
            # Config's resolving properties can import/setup/install a class.
            # Reject other raw selections before invoking either resolver.
            and cfg.settings["worker_class"].value is StagingOwnedWorker
            and cfg.settings["logger_class"].value is StagingGunicornLogger
            and all(getattr(cfg, name) is False for name in
                    ("preload_app", "reload", "reuse_port", "daemon"))
            and cfg.control_socket_disable is True
            and all(type(getattr(cfg, name)) is int and getattr(cfg, name) == 0
                    for name in ("dirty_workers", "max_requests", "max_requests_jitter"))
            and cfg.dirty_apps == [] and cfg.reload_extra_files == []
            and all(type(getattr(cfg, name)) is int and getattr(cfg, name) > 0
                    for name in ("timeout", "graceful_timeout"))
            and all(getattr(cfg, name) is callback for name, callback in _HOOKS.items())
            # Upstream can adopt descriptors instead of creating the configured
            # listener, or notify readiness before a worker loads. Neither path
            # has a reviewed staging contract. Refuse presence, even empty or
            # malformed values, before setup/start; never clear or consume them.
            and not _INHERITED_MASTER_ENV.intersection(os.environ)
            and not _INHERITED_MASTER_ENV.intersection(cfg.env)
            and type(cfg.bind) is list
            and all(type(binding) is str and not binding.startswith("fd://")
                    for binding in cfg.bind)
            and _parser_policy_valid(cfg)
        )
    except Exception:
        return False


class StagingSingleWorkerArbiter(Arbiter):
    """No rolling reload, scaling, reexec, dirty pool, or control socket.

Invalid lifecycle operations halt rather than silently changing state. The
normal master run loop translates HaltServer into shutdown. No replacement is
allowed while an old worker remains registered, including after kill ESRCH:
only upstream waitpid-based reaping retires that registry entry here.

The original heartbeat timeout is retained. It is not a whole-request deadline
or a guarantee against a stalled master, heartbeat filesystem, or OS. SIGKILL
cannot run Python cleanup, and shutdown's final WNOHANG reap may be incomplete.
"""

    def __init__(self, app):
        if (type(app) is not StagingPostForkApplication or not _policy_valid(app.cfg)
                or not app._ready_for_master()):
            raise StagingArbiterConfigurationError("staging_arbiter_configuration_invalid")
        self._owner_pid = os.getpid()
        self._shutdown_started = False
        self._start_called = False
        self._setup_called = False
        self._shutdown_timeout = app.cfg.graceful_timeout
        self._missing_pids = set()
        # Upstream class-level mutable registries must not be shared by instances.
        self.WORKERS = {}
        self.LISTENERS = []
        super().__init__(app)

    def setup(self, app):
        # Upstream setup can preload before any later hook. Do not allow a
        # direct repeated setup to bypass the refused reload operation.
        if self._setup_called:
            self._fail()
        if (type(app) is not StagingPostForkApplication or not _policy_valid(app.cfg)
                or not app._ready_for_master()):
            raise StagingArbiterConfigurationError("staging_arbiter_configuration_invalid")
        self._setup_called = True
        return super().setup(app)

    def _fail(self):
        self._shutdown_started = True
        raise HaltServer("staging_worker_lifecycle_invalid", 1)

    @property
    def num_workers(self):
        return self._num_workers

    @num_workers.setter
    def num_workers(self, value):
        if (type(value) is not int or value != 1
                or self.cfg.nworkers_changed is not NumWorkersChanged.nworkers_changed):
            self._fail()
        # Preserve the reviewed default nworkers_changed hook.
        Arbiter.num_workers.fset(self, value)

    def _check(self):
        if (self._shutdown_started or os.getpid() != self._owner_pid
                or not _policy_valid(self.cfg) or self.num_workers != 1
                or self.worker_class is not StagingOwnedWorker
                or self.timeout != self.cfg.timeout
                or self.cfg.graceful_timeout != self._shutdown_timeout
                or self.master_pid != 0 or self.reexec_pid != 0
                or self.dirty_arbiter_pid != 0 or self._control_server is not None
                or not self.app._ready_for_master() or len(self.WORKERS) > 1):
            self._fail()

    def start(self):
        self._check()
        if self._start_called:
            self._fail()
        self._start_called = True
        return super().start()

    def manage_workers(self):
        self._check()
        return super().manage_workers()

    def spawn_worker(self):
        self._check()
        if self.WORKERS:
            self._fail()
        return super().spawn_worker()

    def stop(self, graceful=True):
        self._shutdown_started = True
        self._prepare_cleanup()
        return super().stop(graceful)

    def _prepare_cleanup(self):
        # Rejected live config must not turn shutdown into arbitrary callbacks
        # or fail before termination due to a broken timeout. Restore only these
        # already-reviewed cleanup inputs, and never resume serving afterward.
        changed = (type(self.cfg.graceful_timeout) is not int
                   or self.cfg.graceful_timeout != self._shutdown_timeout)
        self.cfg.settings["graceful_timeout"].value = self._shutdown_timeout
        for name in ("child_exit", "worker_exit", "on_exit"):
            if getattr(self.cfg, name) is not _HOOKS[name]:
                changed = True
            self.cfg.settings[name].value = _HOOKS[name]
        if changed:
            self._shutdown_started = True
        return changed

    def reap_workers(self):
        already_stopping = self._shutdown_started
        changed = self._prepare_cleanup()
        try:
            result = super().reap_workers()
        finally:
            self._missing_pids.intersection_update(self.WORKERS)
        if changed and not already_stopping:
            self._fail()
        return result

    def halt(self, reason=None, exit_status=0):
        self._shutdown_started = True
        self._prepare_cleanup()
        return super().halt(reason=reason, exit_status=exit_status)

    def kill_worker(self, pid, sig):
        # Unlike upstream, ESRCH does not discard the registry entry. A normal
        # later waitpid can retire it; if that cannot be established, replacement
        # remains blocked. Shutdown may finish with an unresolved entry, which
        # the outer host supervisor must resolve before a new service starts.
        if pid not in self.WORKERS:
            self._fail()
        # ESRCH followed by ECHILD can outlive the original numeric PID. Never
        # signal that number again while retirement is unresolved.
        if pid in self._missing_pids:
            return
        try:
            os.kill(pid, sig)
        except OSError as error:
            if error.errno != errno.ESRCH:
                raise
            self._missing_pids.add(pid)
        else:
            if sig in (signal.SIGTERM, signal.SIGKILL):
                self._stats["workers_killed"] += 1

    def reload(self):
        self._fail()

    def reexec(self):
        self._fail()

    def handle_ttin(self):
        self._fail()

    def handle_ttou(self):
        self._fail()

    def handle_winch(self):
        self._fail()

    def spawn_dirty_arbiter(self):
        self._fail()

    def manage_dirty_arbiter(self):
        self._check()

    def _start_control_server(self):
        self._check()
        # Intentionally never call upstream, even if a future default changes.

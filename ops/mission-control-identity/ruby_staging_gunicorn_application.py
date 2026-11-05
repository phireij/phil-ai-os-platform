"""Opt-in post-fork protected loading and owned cleanup; no serving launcher.

The provider carries only explicit nonsecret startup policy in the master. Its
public load/wsgi methods always refuse. Only the exact owned worker can bind it
once after fork, after which the merged protected-file loader creates the app.
No environment, listener, identity, mount or timeout defaults are selected here.
"""
from __future__ import annotations

import os
import re

from gunicorn.config import Config, PostWorkerInit, WorkerInt, WorkerAbort

from ruby_staging_gunicorn_boundary import StagingCanonicalWorker
from ruby_staging_http_app import StagingHTTPApplication
from ruby_staging_isolated_store import StagingOwnerStartupPolicy
from ruby_staging_protected_files import (StagingFileOwnership,
    create_staging_application_from_files)

_ERROR = "staging_worker_application_invalid"


class StagingWorkerApplicationError(ValueError):
    """Fixed failure, never supplied configuration or secret material."""


def _refuse():
    raise StagingWorkerApplicationError(_ERROR) from None


class StagingPostForkApplication:
    """One-use provider; deliberately not Gunicorn BaseApplication or a CLI.

Disabled construction ignores ownership/generation. Enabled construction only
validates explicit static policy, never effective identity or mounted files.
The parent retains no enabled application or credential. Child loading does not
establish a global singleton, actual mount trust, or a hard startup deadline.
"""

    def __init__(self, cfg, *, enabled=False, ownership=None, expected_generation=None, owner_policy=None):
        try:
            if type(cfg) is not Config or type(enabled) is not bool:
                raise ValueError
            if enabled:
                if (type(ownership) is not StagingFileOwnership
                        or type(expected_generation) is not str
                        or re.fullmatch(r"[0-9a-f]{32}", expected_generation, re.ASCII) is None):
                    raise ValueError
                ownership.validate()
                if owner_policy is not None:
                    if type(owner_policy) is not StagingOwnerStartupPolicy:
                        raise ValueError
                    owner_policy.validate()
                    if (owner_policy.generation != expected_generation or
                            (owner_policy.files.reader_uid, owner_policy.files.reader_gid) !=
                            (ownership.reader_uid, ownership.reader_gid)):
                        raise ValueError
                if (cfg.uid, cfg.gid) != (ownership.reader_uid, ownership.reader_gid):
                    raise ValueError
        except Exception:
            _refuse()
        self.cfg = cfg
        self.callable = None  # Guard compatibility, never a BaseApplication cache.
        self._master_pid = os.getpid()
        self._enabled = enabled
        self._ownership = ownership if enabled else None
        self._reader_identity = (ownership.reader_uid, ownership.reader_gid) if enabled else None
        self._generation = expected_generation if enabled else None
        self._owner_policy = owner_policy if enabled else None
        self._worker_pid = None
        self._worker_identity = None
        self._attempted = False
        self._closed = False
        self._application = None

    def load(self):
        _refuse()

    def wsgi(self):
        _refuse()

    def _ready_for_master(self):
        return (os.getpid() == self._master_pid and self.callable is None
                and self._worker_pid is None and not self._attempted
                and not self._closed and self._application is None)

    def _enter_worker(self, worker):
        if (type(worker) is not StagingOwnedWorker or worker.app is not self
                or worker.cfg is not self.cfg or self.callable is not None
                or self._worker_pid is not None or self._closed
                or worker._creator_pid != self._master_pid
                or (self._enabled and (worker.cfg.uid, worker.cfg.gid) != self._reader_identity)
                or worker.ppid != self._master_pid or os.getppid() != self._master_pid
                or os.getpid() == self._master_pid or worker.pid != os.getpid()):
            _refuse()
        self._worker_pid = os.getpid()
        self._worker_identity = id(worker)

    def _bound(self, worker):
        return (type(worker) is StagingOwnedWorker and id(worker) == self._worker_identity
                and worker.app is self and os.getpid() == self._worker_pid)

    def _load_for_worker(self, worker):
        if (not self._bound(worker) or self._closed or self._attempted
                or os.getppid() != self._master_pid or self.callable is not None):
            _refuse()
        # Failed construction is terminal; no reload/second read of a generation.
        self._attempted = True
        try:
            options = dict(enabled=self._enabled, ownership=self._ownership,
                           expected_generation=self._generation)
            if self._owner_policy is not None:
                options["owner_policy"] = self._owner_policy
            self._application = create_staging_application_from_files(**options)
            if type(self._application) is not StagingHTTPApplication:
                self._application = None
                _refuse()
            return self._application
        except Exception:
            _refuse()
        finally:
            self._ownership = None
            self._generation = None
            self._owner_policy = None

    def _close_for_worker(self, worker):
        # Parent death must not prevent cleanup in the already-bound worker.
        if not self._bound(worker):
            _refuse()
        if self._closed:
            return
        self._closed = True
        application, self._application = self._application, None
        self._ownership = None
        self._generation = None
        self._owner_policy = None
        if application is not None:
            application.close()


class StagingOwnedWorker(StagingCanonicalWorker):
    """Original sync lifecycle with one post-fork app and one cleanup attempt.

Abort/signal methods remain inherited. Cleanup occurs after init/run unwinds,
including normal return after the handler consumed an abort's SystemExit. It is
best effort Python cleanup, not a SIGKILL/OS-crash, secret-erasure or deadline
guarantee. An outer process supervisor still has to handle blocked cleanup.
"""

    def __init__(self, age, ppid, sockets, app, timeout, cfg, log):
        if (type(self) is not StagingOwnedWorker or type(app) is not StagingPostForkApplication
                or app.cfg is not cfg or app._master_pid != os.getpid()
                or ppid != os.getpid() or not app._ready_for_master()):
            _refuse()
        self._creator_pid = os.getpid()
        self._init_attempted = False
        self._init_active = False
        self._run_attempted = False
        self._provider_entered = False
        super().__init__(age, ppid, sockets, app, timeout, cfg, log)

    def load_wsgi(self):
        if not self._provider_entered or not self._init_active or not self._policy_valid():
            _refuse()
        self.wsgi = self.app._load_for_worker(self)
        # Upstream invokes post_worker_init immediately after this returns.
        if not self._policy_valid():
            _refuse()

    def _policy_valid(self):
        if type(self.cfg) is not Config:
            return False
        return (type(self.cfg.workers) is int and self.cfg.workers == 1
                and type(self.cfg.threads) is int and self.cfg.threads == 1
                and self.cfg.reload is False and self.cfg.preload_app is False
                and self.cfg.post_worker_init is PostWorkerInit.post_worker_init
                and self.cfg.worker_int is WorkerInt.worker_int
                and self.cfg.worker_abort is WorkerAbort.worker_abort)

    def run(self):
        if (not self._init_active or not self._provider_entered or self._run_attempted
                or not self.app._bound(self) or self.app._closed
                or os.getppid() != self.ppid or not self._policy_valid()
                or self.wsgi is not self.app._application
                or type(self.wsgi) is not StagingHTTPApplication):
            _refuse()
        self._run_attempted = True
        return super().run()

    def init_process(self):
        if (self._init_attempted or os.getpid() == self._creator_pid
                or os.getppid() != self.ppid or self.pid != os.getpid()
                or not self._policy_valid()):
            _refuse()
        self._init_attempted = True
        self._init_active = True
        primary = cleanup = None
        try:
            self.app._enter_worker(self)
            self._provider_entered = True
            super().init_process()
        except BaseException as failure:
            primary = failure
        finally:
            self.alive = False
            self._init_active = False
            self.wsgi = None
            if self._provider_entered:
                try:
                    self.app._close_for_worker(self)
                except BaseException as failure:
                    cleanup = failure
        # Preserve control flow without rendering exception text. A primary
        # control outranks cleanup; otherwise a cleanup control outranks an
        # ordinary failure. Ordinary failures are fixed and unchained.
        if primary is not None and not isinstance(primary, Exception):
            raise primary
        if cleanup is not None and not isinstance(cleanup, Exception):
            raise cleanup
        if primary is not None or cleanup is not None:
            _refuse()

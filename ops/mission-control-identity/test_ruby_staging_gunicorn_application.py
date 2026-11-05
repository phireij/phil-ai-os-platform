"""Actual post-fork loader/factory ownership with inert process/HTTP boundaries."""
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("owned_arbiter_fixtures",
    ROOT / "test_ruby_staging_gunicorn_arbiter.py")
fixtures = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fixtures
spec.loader.exec_module(fixtures)
base = fixtures.base
from gunicorn.workers.base import Worker
from gunicorn.workers.sync import SyncWorker
from ruby_staging_gunicorn_application import (StagingPostForkApplication,
    StagingOwnedWorker, StagingWorkerApplicationError)
import ruby_staging_gunicorn_application as owned
from ruby_staging_gunicorn_logging import StagingGunicornLogger
from ruby_staging_http_app import StagingHTTPApplication
import ruby_staging_protected_files as loader
import test_ruby_staging_protected_files as protected

ERROR = "staging_worker_application_invalid"


class OwnedApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        protected.ProtectedFilesTests.setUpClass()

    def setUp(self):
        fixtures.SingleWorkerTests.setUp(self)
        self.fx = protected.ProtectedFilesTests("test_real_factory_signed_login_read_and_logout")
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.parent = os.getpid()
        self.child = self.parent + 100000

    assert_no_network = fixtures.SingleWorkerTests.assert_no_network

    def provider(self, *, enabled=False, **changes):
        cfg = fixtures.SingleWorkerTests.app(self).cfg
        cfg.set("user", os.geteuid())
        cfg.set("group", os.getegid())
        options = dict(enabled=enabled, ownership=self.fx.ownership,
                       expected_generation=protected.GENERATION)
        options.update(changes)
        return StagingPostForkApplication(cfg, **options)

    def worker(self, provider=None):
        provider = provider or self.provider()
        tmp = SimpleNamespace(fileno=lambda: 987, close=Mock())
        with patch("gunicorn.workers.base.WorkerTmp", return_value=tmp):
            worker = StagingOwnedWorker(1, self.parent, [], provider, 1,
                                       provider.cfg, StagingGunicornLogger(provider.cfg))
        worker.pid = self.child
        return worker

    @contextmanager
    def child_context(self, worker, run=None):
        # Actual original init_process ordering, but no owner change, pipe,
        # signal installation, socket, real worker or serving loop.
        with patch("os.getpid", return_value=self.child), patch("os.getppid", return_value=self.parent), \
                patch("gunicorn.workers.base.util.set_owner_process") as set_owner, \
                patch("gunicorn.workers.base.util.seed"), patch("os.pipe", return_value=(987, 988)), \
                patch("gunicorn.workers.base.util.set_non_blocking"), \
                patch("gunicorn.workers.base.util.close_on_exec"), \
                patch.object(worker, "init_signals"), patch.object(worker.log, "close_on_exec"), \
                patch.object(SyncWorker, "run", side_effect=run) as run_mock:
            yield set_owner, run_mock

    @contextmanager
    def real_files(self):
        # Same actual descriptor-bound synthetic tree as the merged loader
        # tests. Read-only mount flags and clocks are explicitly simulated.
        original = owned.create_staging_application_from_files
        def load(**kwargs):
            return original(**kwargs, wall_clock=lambda: self.fx.wall,
                            monotonic_clock=lambda: self.fx.mono)
        with self.fx.filesystem(), patch.object(owned, "create_staging_application_from_files", side_effect=load):
            yield

    def assert_terminal(self, worker):
        self.assertFalse(worker.alive)
        self.assertFalse(worker._init_active)
        self.assertIsNone(worker.wsgi)
        self.assertTrue(worker.app._closed)
        self.assertIsNone(worker.app._application)
        self.assertIsNone(worker.app._ownership)
        self.assertIsNone(worker.app._generation)

    def test_provider_and_worker_constructor_never_load(self):
        with patch.object(owned, "create_staging_application_from_files") as load:
            provider = self.provider(enabled=True)
            worker = self.worker(provider)
        load.assert_not_called()
        self.assertIsNone(provider.callable)
        self.assertIsNone(provider._application)
        self.assertFalse(worker._init_attempted)

    def test_disabled_provider_ignores_poison_policy_and_opens_nothing(self):
        class Poison:
            def __getattribute__(self, name):
                raise AssertionError("unused_input_inspected")
        provider = self.provider(ownership=Poison(), expected_generation=Poison())
        worker = self.worker(provider)
        with patch.object(loader.os, "open") as opened, \
                patch.object(base.requests, "Session") as session, self.child_context(worker):
            worker.init_process()
        opened.assert_not_called()
        session.assert_not_called()
        self.assert_terminal(worker)

    def test_master_direct_and_check_config_loading_always_refuse(self):
        provider = self.provider(enabled=True)
        with patch.object(owned, "create_staging_application_from_files") as load:
            for method in (provider.load, provider.wsgi):
                with self.assertRaisesRegex(StagingWorkerApplicationError, "^" + ERROR + "$"):
                    method()
            with patch("os.getpid", return_value=self.child), patch("os.getppid", return_value=self.parent):
                for method in (provider.load, provider.wsgi):
                    with self.assertRaises(StagingWorkerApplicationError):
                        method()
        load.assert_not_called()

    def test_invalid_enabled_policy_and_identity_never_load(self):
        for changes in ({"enabled": 1}, {"enabled": None}, {"enabled": True, "ownership": None},
                        {"enabled": True, "expected_generation": "private-invalid"}):
            with self.subTest(changes=changes), self.assertRaises(StagingWorkerApplicationError):
                self.provider(**changes)
        cfg = fixtures.SingleWorkerTests.app(self).cfg
        cfg.set("user", self.fx.ownership.reader_uid + 1)
        with self.assertRaises(StagingWorkerApplicationError):
            StagingPostForkApplication(cfg, enabled=True, ownership=self.fx.ownership,
                                       expected_generation=protected.GENERATION)

    def test_wrong_provider_or_preloaded_cache_rejected_before_workertmp(self):
        provider = self.provider()
        cfg = provider.cfg
        for app in (SimpleNamespace(cfg=cfg), self.provider()):
            with patch("gunicorn.workers.base.WorkerTmp") as tmp, \
                    self.assertRaises(StagingWorkerApplicationError):
                StagingOwnedWorker(1, self.parent, [], app, 1, cfg, StagingGunicornLogger(cfg))
            tmp.assert_not_called()
        provider.callable = object()
        with patch("gunicorn.workers.base.WorkerTmp") as tmp, self.assertRaises(StagingWorkerApplicationError):
            StagingOwnedWorker(1, self.parent, [], provider, 1, cfg, StagingGunicornLogger(cfg))
        tmp.assert_not_called()

    def test_master_wrong_parent_or_worker_pid_cannot_enter_init(self):
        for current, parent, pid in ((self.parent, self.parent, self.parent),
                (self.child, self.parent + 1, self.child), (self.child, self.parent, self.child + 1)):
            worker = self.worker()
            worker.pid = pid
            with patch("os.getpid", return_value=current), patch("os.getppid", return_value=parent), \
                    patch.object(Worker, "init_process") as init, self.assertRaises(StagingWorkerApplicationError):
                worker.init_process()
            init.assert_not_called()

    def test_direct_load_and_run_refuse_before_initialization(self):
        worker = self.worker()
        with self.child_context(worker) as (_, run), patch.object(owned, "create_staging_application_from_files") as load:
            for method in (worker.load_wsgi, worker.run):
                with self.assertRaises(StagingWorkerApplicationError):
                    method()
        run.assert_not_called()
        load.assert_not_called()

    def test_real_loader_factory_signed_review_is_closed_after_original_init_returns(self):
        worker = self.worker(self.provider(enabled=True))
        apps, sessions = [], []
        def run():
            apps.append(worker.wsgi)
            self.assertTrue(worker.booted)
            self.assertEqual(self.fx.live, {})
            session, _, _, _ = self.fx.login(worker.wsgi)
            sessions.append(session)
            status, _, body = self.fx.call(worker.wsgi, "/api/ruby-review-synthetic", cookie=session)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["authority"], "none")
        with self.real_files(), self.child_context(worker, run=run) as (set_owner, run_mock):
            worker.init_process()
            set_owner.assert_called_once()
            run_mock.assert_called_once_with()
        self.assertEqual(len(self.fx.closed), 6)
        self.assertTrue(apps[0]._closed)
        self.assertEqual(self.fx.call(apps[0], "/api/session", cookie=sessions[0])[0], 503)
        self.assert_terminal(worker)

    def test_original_identity_step_precedes_real_loader(self):
        worker = self.worker(self.provider(enabled=True))
        with self.real_files(), self.child_context(worker) as (set_owner, _):
            original = owned.create_staging_application_from_files
            def load(**kwargs):
                set_owner.assert_called_once()
                return original(**kwargs)
            with patch.object(owned, "create_staging_application_from_files", side_effect=load):
                worker.init_process()
        self.assert_terminal(worker)

    def test_invalid_file_generation_fails_before_session_or_run(self):
        self.fx.write("secret.json", json.dumps({**self.fx.secret, "generation": "b2" * 16}).encode())
        worker = self.worker(self.provider(enabled=True))
        with self.real_files(), self.child_context(worker) as (_, run), patch.object(base.requests, "Session") as session:
            with self.assertRaises(StagingWorkerApplicationError):
                worker.init_process()
        session.assert_not_called()
        run.assert_not_called()
        self.assertEqual(len(self.fx.closed), 6)
        self.assert_terminal(worker)

    def test_loader_failure_is_fixed_and_never_retried(self):
        worker = self.worker()
        with self.child_context(worker), patch.object(owned, "create_staging_application_from_files",
                side_effect=RuntimeError("SYNTHETIC_PRIVATE")) as load:
            for _ in range(2):
                with self.assertRaises(StagingWorkerApplicationError) as caught:
                    worker.init_process()
                self.assertNotIn("SYNTHETIC_PRIVATE", "".join(traceback.format_exception(caught.exception)))
            load.assert_called_once()
        self.assert_terminal(worker)

    def test_duplicate_load_and_run_refuse_with_one_application(self):
        worker = self.worker()
        app = StagingHTTPApplication()
        def run():
            for method in (worker.load_wsgi, worker.run):
                with self.assertRaises(StagingWorkerApplicationError):
                    method()
        with self.child_context(worker, run=run), \
                patch.object(owned, "create_staging_application_from_files", return_value=app) as load, \
                patch.object(app, "close", wraps=app.close) as close:
            worker.init_process()
        load.assert_called_once()
        close.assert_called_once()
        self.assert_terminal(worker)

    def test_failure_before_load_still_finalizes_provider(self):
        worker = self.worker()
        with self.child_context(worker), patch.object(Worker, "init_process", side_effect=RuntimeError("private")), \
                patch.object(owned, "create_staging_application_from_files") as load:
            with self.assertRaises(StagingWorkerApplicationError):
                worker.init_process()
        load.assert_not_called()
        self.assert_terminal(worker)

    def test_failure_after_load_before_run_closes_application(self):
        worker = self.worker()
        app = StagingHTTPApplication()
        def init(_worker):
            _worker.load_wsgi()
            raise RuntimeError("SYNTHETIC_POST_INIT")
        with self.child_context(worker), patch.object(Worker, "init_process", init), \
                patch.object(owned, "create_staging_application_from_files", return_value=app), \
                patch.object(app, "close", wraps=app.close) as close:
            with self.assertRaises(StagingWorkerApplicationError):
                worker.init_process()
        close.assert_called_once()
        self.assert_terminal(worker)

    def test_run_failure_redacted_and_control_precedence_preserved(self):
        cases = ((RuntimeError("private"), None, StagingWorkerApplicationError),
            (SystemExit(7), RuntimeError("cleanup"), SystemExit),
            (KeyboardInterrupt("primary"), SystemExit(8), KeyboardInterrupt),
            (GeneratorExit(), KeyboardInterrupt(), GeneratorExit),
            (RuntimeError("private"), SystemExit(9), SystemExit),
            (None, RuntimeError("cleanup"), StagingWorkerApplicationError),
            (None, SystemExit(10), SystemExit))
        for primary, cleanup, expected in cases:
            worker = self.worker()
            app = StagingHTTPApplication()
            with self.subTest(primary=type(primary), cleanup=type(cleanup)), \
                    self.child_context(worker, run=primary), \
                    patch.object(owned, "create_staging_application_from_files", return_value=app), \
                    patch.object(app, "close", side_effect=cleanup) as close:
                with self.assertRaises(expected) as caught:
                    worker.init_process()
                if primary is not None and not isinstance(primary, Exception):
                    self.assertIs(caught.exception, primary)
                elif cleanup is not None and not isinstance(cleanup, Exception):
                    self.assertIs(caught.exception, cleanup)
                close.assert_called_once()
                self.assert_terminal(worker)
                worker.app._close_for_worker(worker)
                close.assert_called_once()

    def test_parent_loss_after_load_does_not_block_owned_cleanup(self):
        worker = self.worker()
        app = StagingHTTPApplication()
        def run():
            parent_mock.return_value = self.parent + 1
        with self.child_context(worker, run=run), patch("os.getppid", return_value=self.parent) as parent_mock, \
                patch.object(owned, "create_staging_application_from_files", return_value=app):
            worker.init_process()
        self.assertTrue(app._closed)
        self.assert_terminal(worker)

    def test_abort_consumed_by_actual_handler_still_closes_on_normal_return(self):
        worker = self.worker()
        app = StagingHTTPApplication()
        client = base.MemorySocket(b"GET /healthz HTTP/1.1\r\nHost: staging.example.invalid\r\n\r\n")
        def run():
            with patch.object(app, "__call__", side_effect=AssertionError("unused")):
                # Instance special-method patches do not replace __call__. Use
                # the class only for the duration of the synthetic request.
                with patch.object(StagingHTTPApplication, "__call__",
                        side_effect=lambda *a: worker.handle_abort(signal.SIGABRT, None)):
                    worker.handle(base.MemorySocket(), client, ("127.0.0.1", 12345))
            self.assertFalse(worker.alive)
        with self.child_context(worker, run=run), \
                patch.object(owned, "create_staging_application_from_files", return_value=app):
            worker.init_process()
        self.assertIn(b"500 Internal Server Error", bytes(client.outgoing))
        self.assertTrue(app._closed)
        self.assert_terminal(worker)

    def test_original_abort_and_signal_methods_remain_inherited(self):
        self.assertIs(StagingOwnedWorker.handle_abort, Worker.handle_abort)
        self.assertIs(StagingOwnedWorker.init_signals, Worker.init_signals)

    def test_abort_after_response_headers_closes_application_without_second_response(self):
        worker = self.worker()
        app = StagingHTTPApplication()
        client = base.MemorySocket(b"GET /healthz HTTP/1.1\r\nHost: staging.example.invalid\r\n\r\n")
        def response(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])
            def chunks():
                yield b"synthetic partial response"
                worker.handle_abort(signal.SIGABRT, None)
            return chunks()
        def run():
            with patch.object(StagingHTTPApplication, "__call__", side_effect=response):
                worker.handle(base.MemorySocket(), client, ("127.0.0.1", 12345))
        with self.child_context(worker, run=run), \
                patch.object(owned, "create_staging_application_from_files", return_value=app):
            worker.init_process()
        self.assertIn(b"200 OK", bytes(client.outgoing))
        self.assertNotIn(b"500 Internal Server Error", bytes(client.outgoing))
        self.assertTrue(app._closed)
        self.assert_terminal(worker)

    def test_failed_cleanup_is_not_retried_or_reloaded_after_finalization(self):
        worker = self.worker()
        app = StagingHTTPApplication()
        with self.child_context(worker), \
                patch.object(owned, "create_staging_application_from_files", return_value=app) as load, \
                patch.object(app, "close", side_effect=RuntimeError("SYNTHETIC_CLOSE")) as close:
            with self.assertRaises(StagingWorkerApplicationError):
                worker.init_process()
            worker.app._close_for_worker(worker)
            for method in (worker.init_process, worker.load_wsgi, worker.run):
                with self.assertRaises(StagingWorkerApplicationError):
                    method()
            load.assert_called_once()
            close.assert_called_once()
        self.assert_terminal(worker)

    def test_changed_post_load_hook_is_not_invoked_before_cleanup(self):
        worker = self.worker()
        app = StagingHTTPApplication()
        hook = Mock(side_effect=AssertionError("untrusted_hook_invoked"))
        def load(**kwargs):
            worker.cfg.settings["post_worker_init"].value = hook
            return app
        with self.child_context(worker) as (_, run), \
                patch.object(owned, "create_staging_application_from_files", side_effect=load):
            with self.assertRaises(StagingWorkerApplicationError):
                worker.init_process()
        hook.assert_not_called()
        run.assert_not_called()
        self.assertTrue(app._closed)
        self.assert_terminal(worker)

    def test_parent_loss_during_loading_refuses_serving_but_closes_app(self):
        worker = self.worker()
        app = StagingHTTPApplication()
        def load(**kwargs):
            parent_mock.return_value = self.parent + 1
            return app
        with self.child_context(worker) as (_, run), \
                patch("os.getppid", return_value=self.parent) as parent_mock, \
                patch.object(owned, "create_staging_application_from_files", side_effect=load):
            with self.assertRaises(StagingWorkerApplicationError):
                worker.init_process()
        run.assert_not_called()
        self.assertTrue(app._closed)
        self.assert_terminal(worker)


if __name__ == "__main__":
    unittest.main(verbosity=2)

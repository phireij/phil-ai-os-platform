"""Pinned original arbiter methods with inert process boundaries, never a server."""
import errno
import importlib.util
import itertools
import os
from pathlib import Path
import signal
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("arbiter_offline_support",
    ROOT / "ruby_staging_server_test_support.py")
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
from gunicorn.arbiter import Arbiter
from gunicorn.config import Config
from gunicorn.ctl.handlers import CommandHandlers
from gunicorn.errors import HaltServer
from ruby_staging_gunicorn_arbiter import (StagingSingleWorkerArbiter,
    StagingArbiterConfigurationError, _HOOKS)
from ruby_staging_gunicorn_boundary import StagingCanonicalWorker
from ruby_staging_gunicorn_application import StagingOwnedWorker, StagingPostForkApplication
from ruby_staging_gunicorn_logging import StagingGunicornLogger

UPSTREAM_RUN = Arbiter.run


def forbidden(*args, **kwargs):
    raise AssertionError("real_process_or_server_operation_forbidden")


class SingleWorkerTests(unittest.TestCase):
    def setUp(self):
        # Never invoke a real fork, signal, wait, listener, or server loop.
        for target in ("os.fork", "os.kill", "os.waitpid", "gunicorn.arbiter.Arbiter.start",
                       "gunicorn.arbiter.Arbiter.run"):
            guard = patch(target, side_effect=forbidden)
            guard.start()
            self.addCleanup(guard.stop)
        self.addCleanup(self.assert_no_network)

    def assert_no_network(self):
        self.assertEqual(base.DENIED, [{"event": "socket.__new__", "phase": "imports",
            "urllib3_import_capability_probe": True}])

    def app(self, **overrides):
        cfg = Config()
        settings = dict(workers=1, threads=1, worker_class=StagingOwnedWorker,
            logger_class=StagingGunicornLogger, http_parser="python", header_map="refuse",
            forwarder_headers="", control_socket_disable=True, preload_app=False,
            reload=False, max_requests=0, reuse_port=False, daemon=False,
            dirty_apps=[], dirty_workers=0, bind=[], forwarded_allow_ips="",
            proxy_allow_ips="", errorlog="-", accesslog=None, raw_env=[],
            timeout=30, graceful_timeout=30)
        settings.update(overrides)
        for name, value in settings.items():
            cfg.set(name, value)
        cfg.validate()
        app = StagingPostForkApplication(cfg)
        app.wsgi = Mock(side_effect=forbidden)
        return app

    def arbiter(self):
        arb = StagingSingleWorkerArbiter(self.app())
        arb.pid = os.getpid()
        return arb

    def fake_worker(self, *, last_update=0, aborted=False):
        return SimpleNamespace(age=1, aborted=aborted, tmp=SimpleNamespace(
            last_update=Mock(return_value=last_update), close=Mock()))

    def test_safe_constructor_does_not_load_application_or_start_server(self):
        app = self.app()
        arb = StagingSingleWorkerArbiter(app)
        app.wsgi.assert_not_called()
        self.assertEqual((arb.num_workers, arb.WORKERS, arb.LISTENERS), (1, {}, []))
        self.assertFalse(arb._start_called)

    def test_unsafe_configuration_rejected_before_upstream_setup(self):
        cases = dict(workers=2, threads=2, worker_class="sync", logger_class="simple",
            preload_app=True, reload=True, reuse_port=True, daemon=True,
            control_socket_disable=False, max_requests=1, max_requests_jitter=1,
            dirty_workers=1, dirty_apps=["synthetic:app"], reload_extra_files=[__file__],
            timeout=0, graceful_timeout=0, header_map="drop")
        for name, value in cases.items():
            with self.subTest(name=name):
                app = self.app(**{name: value})
                with patch.object(Arbiter, "__init__") as init:
                    with self.assertRaisesRegex(StagingArbiterConfigurationError,
                                                "^staging_arbiter_configuration_invalid$"):
                        StagingSingleWorkerArbiter(app)
                    init.assert_not_called()

    def test_preloaded_application_rejected_before_upstream_setup(self):
        app = self.app()
        app.callable = Mock()
        with patch.object(Arbiter, "__init__") as init:
            with self.assertRaises(StagingArbiterConfigurationError):
                StagingSingleWorkerArbiter(app)
            init.assert_not_called()

    def test_stale_or_foreign_provider_rejected_before_upstream_setup(self):
        for field, value in (("_master_pid", -1), ("_worker_pid", 12345),
                ("_attempted", True), ("_closed", True), ("_application", object())):
            app = self.app()
            setattr(app, field, value)
            with self.subTest(field=field), patch.object(Arbiter, "__init__") as init:
                with self.assertRaises(StagingArbiterConfigurationError):
                    StagingSingleWorkerArbiter(app)
                init.assert_not_called()

    def test_custom_process_hooks_rejected(self):
        for name in _HOOKS:
            app = self.app()
            app.cfg.settings[name].value = lambda *args: None
            with self.subTest(hook=name), self.assertRaises(StagingArbiterConfigurationError):
                StagingSingleWorkerArbiter(app)

    def test_unapproved_class_resolver_hooks_never_execute(self):
        class UnapprovedWorker:
            setup = Mock(side_effect=forbidden)
        class UnapprovedLogger:
            install = Mock(side_effect=forbidden)
        for setting, cls in (("worker_class", UnapprovedWorker), ("logger_class", UnapprovedLogger)):
            with self.subTest(setting=setting), self.assertRaises(StagingArbiterConfigurationError):
                StagingSingleWorkerArbiter(self.app(**{setting: cls}))
        UnapprovedWorker.setup.assert_not_called()
        UnapprovedLogger.install.assert_not_called()

    def test_changed_worker_count_hook_rejected_before_invocation(self):
        arb = self.arbiter()
        hook = Mock(side_effect=forbidden)
        arb.cfg.settings["nworkers_changed"].value = hook
        with self.assertRaises(HaltServer):
            arb.num_workers = 1
        hook.assert_not_called()
        self.assertEqual(arb.num_workers, 1)

    def test_inherited_reexec_environment_rejected_without_rendering(self):
        for name in ("GUNICORN_PID", "GUNICORN_FD"):
            with patch.dict(os.environ, {name: "SYNTHETIC_PRIVATE"}):
                with self.assertRaises(StagingArbiterConfigurationError):
                    StagingSingleWorkerArbiter(self.app())
            with self.assertRaises(StagingArbiterConfigurationError):
                StagingSingleWorkerArbiter(self.app(raw_env=[name + "=SYNTHETIC_PRIVATE"]))

    def test_registries_are_per_instance(self):
        first, second = self.arbiter(), self.arbiter()
        first.WORKERS[12345] = self.fake_worker()
        first.LISTENERS.append(object())
        self.assertEqual(second.WORKERS, {})
        self.assertEqual(second.LISTENERS, [])
        self.assertIsNot(first.WORKERS, Arbiter.WORKERS)

    def test_scale_property_fails_before_mutating_or_running_hook(self):
        for value in (0, 2, True, 1.0, "1", None):
            arb = self.arbiter()
            with self.subTest(value=value), self.assertRaises(HaltServer):
                arb.num_workers = value
            self.assertEqual(arb.num_workers, 1)
            self.assertTrue(arb._shutdown_started)

    def test_actual_control_add_cannot_scale_even_with_unchanged_cfg(self):
        arb = self.arbiter()
        with patch.object(arb, "wakeup") as wake, self.assertRaises(HaltServer):
            CommandHandlers(arb).worker_add(1)
        self.assertEqual((arb.num_workers, arb.cfg.workers), (1, 1))
        wake.assert_not_called()

    def test_negative_control_upstream_ttin_can_diverge_from_wsgi_worker_flag(self):
        arb = Arbiter(self.app())
        arb.WORKERS = {}
        with patch.object(arb, "manage_workers") as manage:
            arb.handle_ttin()
        self.assertEqual((arb.num_workers, arb.cfg.workers), (2, 1))
        from gunicorn.http.wsgi import base_environ
        self.assertIs(base_environ(arb.cfg)["wsgi.multiprocess"], False)
        manage.assert_called_once_with()

    def test_negative_control_upstream_reload_spawns_before_retirement(self):
        app = self.app()
        app.reload = Mock()
        arb = Arbiter(app)
        arb.pid = os.getpid()
        arb.WORKERS = {12345: self.fake_worker()}
        events = []
        def spawn():
            self.assertIn(12345, arb.WORKERS)
            events.append("spawn_with_old_registered")
            arb.WORKERS[12346] = self.fake_worker()
        def manage():
            self.assertEqual(len(arb.WORKERS), 2)
            events.append("manage_after_overlap")
        with patch.object(arb, "spawn_worker", side_effect=spawn), \
                patch.object(arb, "manage_workers", side_effect=manage), \
                patch.object(arb.log, "reopen_files"), \
                patch("gunicorn.arbiter.util._setproctitle"), \
                patch("gunicorn.arbiter.time.monotonic", side_effect=[0, 31]):
            arb.reload()
        self.assertEqual(events, ["spawn_with_old_registered", "manage_after_overlap"])

    def test_reload_reexec_scaling_and_dirty_paths_halt_before_side_effect(self):
        for method in ("reload", "reexec", "handle_hup", "handle_usr2", "handle_ttin",
                       "handle_ttou", "handle_winch", "spawn_dirty_arbiter"):
            arb = self.arbiter()
            with self.subTest(method=method), self.assertRaises(HaltServer) as caught:
                getattr(arb, method)()
            self.assertEqual(caught.exception.reason, "staging_worker_lifecycle_invalid")
            self.assertEqual(arb._stats["reloads"], 0)
            self.assertTrue(arb._shutdown_started)

    def test_control_and_dirty_maintenance_are_validated_noops(self):
        arb = self.arbiter()
        with patch.object(Arbiter, "_start_control_server", side_effect=forbidden), \
                patch.object(Arbiter, "manage_dirty_arbiter", side_effect=forbidden):
            arb._start_control_server()
            arb.manage_dirty_arbiter()
        self.assertIsNone(arb._control_server)
        arb.cfg.set("control_socket_disable", False)
        with self.assertRaises(HaltServer):
            arb._start_control_server()

    def test_runtime_mutation_stops_before_start_manage_or_spawn(self):
        mutations = (lambda a: a.cfg.set("preload_app", True),
            lambda a: a.cfg.set("graceful_timeout", 31),
            lambda a: setattr(a, "worker_class", object),
            lambda a: setattr(a, "timeout", 0),
            lambda a: setattr(a, "master_pid", 123),
            lambda a: setattr(a, "reexec_pid", 123),
            lambda a: setattr(a, "dirty_arbiter_pid", 123),
            lambda a: setattr(a, "_control_server", object()),
            lambda a: setattr(a.app, "callable", object()),
            lambda a: setattr(a, "_owner_pid", -1))
        for mutation in mutations:
            for operation in ("start", "manage_workers", "spawn_worker"):
                arb = self.arbiter()
                mutation(arb)
                with self.subTest(mutation=mutation, operation=operation), self.assertRaises(HaltServer):
                    getattr(arb, operation)()

    def test_start_is_one_shot_even_if_upstream_start_returns(self):
        arb = self.arbiter()
        with patch.object(Arbiter, "start") as start:
            arb.start()
            start.assert_called_once_with()
            with self.assertRaises(HaltServer):
                arb.start()
            start.assert_called_once_with()

    def test_repeated_setup_cannot_preload_or_reset_shutdown(self):
        arb = self.arbiter()
        app = self.app(preload_app=True)
        with patch.object(Arbiter, "setup", side_effect=forbidden):
            with self.assertRaises(HaltServer):
                arb.setup(app)
        app.wsgi.assert_not_called()
        self.assertTrue(arb._shutdown_started)

    def test_manage_does_not_replace_registered_worker(self):
        arb = self.arbiter()
        arb.WORKERS[12345] = self.fake_worker()
        with patch.object(Arbiter, "spawn_worker", side_effect=forbidden):
            arb.manage_workers()
            with self.assertRaises(HaltServer):
                arb.spawn_worker()

    def test_spawn_delegates_once_only_when_registry_empty(self):
        arb = self.arbiter()
        def register():
            arb.WORKERS[12345] = self.fake_worker()
            return 12345
        with patch.object(Arbiter, "spawn_worker", side_effect=register) as spawn, \
                patch("gunicorn.arbiter.time.sleep"):
            arb.manage_workers()
            arb.manage_workers()
        spawn.assert_called_once_with()

    def test_original_spawn_parent_branch_registers_one_worker_and_waits_for_reap(self):
        arb = self.arbiter()
        with patch("os.fork", return_value=12345) as fork, \
                patch("gunicorn.arbiter.time.sleep"), \
                patch("gunicorn.workers.base.WorkerTmp", return_value=SimpleNamespace(close=Mock())):
            arb.manage_workers()
            self.assertEqual(list(arb.WORKERS), [12345])
            worker = arb.WORKERS[12345]
            self.addCleanup(worker.tmp.close)
            self.assertIs(type(worker), StagingOwnedWorker)
            self.assertEqual(worker.pid, 12345)
            self.assertEqual(arb._stats["workers_spawned"], 1)
            arb.manage_workers()
            with self.assertRaises(HaltServer):
                arb.spawn_worker()
            fork.assert_called_once_with()
        arb.app.wsgi.assert_not_called()

    def test_original_run_dispatch_translates_refused_signals_to_halt(self):
        for sig in (signal.SIGHUP, signal.SIGUSR2, signal.SIGTTIN,
                    signal.SIGTTOU, signal.SIGWINCH):
            arb = self.arbiter()
            with self.subTest(signal=sig), patch.object(arb, "start"), \
                    patch.object(arb, "manage_workers"), \
                    patch.object(arb, "wait_for_signals", return_value=[sig]), \
                    patch("gunicorn.arbiter.util._setproctitle"), \
                    patch.object(arb, "halt", side_effect=SystemExit(1)) as halt:
                with self.assertRaises(SystemExit) as caught:
                    UPSTREAM_RUN(arb)
                self.assertEqual(caught.exception.code, 1)
                halt.assert_called_once_with(reason="staging_worker_lifecycle_invalid", exit_status=1)
            self.assertTrue(arb._shutdown_started)

    def test_existing_multiple_workers_halt_without_forking(self):
        arb = self.arbiter()
        arb.WORKERS = {12345: self.fake_worker(), 12346: self.fake_worker()}
        with self.assertRaises(HaltServer):
            arb.manage_workers()

    def test_esrch_retains_worker_until_actual_reaper_reports_exit(self):
        arb = self.arbiter()
        worker = self.fake_worker()
        arb.WORKERS[12345] = worker
        with patch("os.kill", side_effect=ProcessLookupError(errno.ESRCH, "synthetic")):
            arb.kill_worker(12345, signal.SIGKILL)
        self.assertIs(arb.WORKERS[12345], worker)
        worker.tmp.close.assert_not_called()
        with patch.object(Arbiter, "spawn_worker", side_effect=forbidden):
            arb.manage_workers()
        with patch("os.waitpid", side_effect=[(12345, 0), (0, 0)]) as wait:
            arb.reap_workers()
        self.assertEqual(arb.WORKERS, {})
        self.assertEqual(arb._missing_pids, set())
        worker.tmp.close.assert_called_once_with()
        self.assertEqual(wait.call_args_list[0].args, (-1, os.WNOHANG))
        with patch.object(Arbiter, "spawn_worker", return_value=12346) as spawn:
            arb.spawn_worker()
            spawn.assert_called_once_with()
        # A legitimately new child can reuse the number only after retirement.
        arb.WORKERS[12345] = self.fake_worker()
        with patch("os.kill") as kill:
            arb.kill_worker(12345, signal.SIGTERM)
        kill.assert_called_once_with(12345, signal.SIGTERM)

    def test_esrch_and_echild_leave_unresolved_registry_closed(self):
        arb = self.arbiter()
        arb.WORKERS[12345] = self.fake_worker()
        with patch("os.kill", side_effect=ProcessLookupError(errno.ESRCH, "synthetic")):
            arb.kill_worker(12345, signal.SIGTERM)
        with patch("os.waitpid", side_effect=ChildProcessError(errno.ECHILD, "synthetic")):
            arb.reap_workers()
        self.assertIn(12345, arb.WORKERS)
        with patch.object(Arbiter, "spawn_worker", side_effect=forbidden):
            arb.manage_workers()
        with patch("os.kill", side_effect=forbidden):
            arb.kill_worker(12345, signal.SIGABRT)
            arb.kill_worker(12345, signal.SIGKILL)
        self.assertEqual(arb._missing_pids, {12345})

    def test_changed_child_exit_is_suppressed_before_reaping_and_halts(self):
        arb = self.arbiter()
        worker = self.fake_worker()
        arb.WORKERS[12345] = worker
        hook = Mock(side_effect=forbidden)
        arb.cfg.settings["child_exit"].value = hook
        with patch("os.waitpid", side_effect=[(12345, 0), (0, 0)]):
            with self.assertRaises(HaltServer):
                arb.reap_workers()
        hook.assert_not_called()
        worker.tmp.close.assert_called_once_with()
        self.assertEqual(arb.WORKERS, {})
        self.assertTrue(arb._shutdown_started)

    def test_invalid_shutdown_timeout_and_exit_hooks_cannot_skip_termination(self):
        arb = self.arbiter()
        arb.WORKERS[12345] = self.fake_worker()
        hooks = [Mock(side_effect=forbidden) for _ in range(3)]
        for name, hook in zip(("child_exit", "worker_exit", "on_exit"), hooks):
            arb.cfg.settings[name].value = hook
        arb.cfg.settings["graceful_timeout"].value = None
        with patch("gunicorn.arbiter.sock.close_sockets"), patch("os.kill") as kill, \
                patch("gunicorn.arbiter.time.time", side_effect=itertools.chain([0], itertools.repeat(31))), \
                patch("os.waitpid", side_effect=[(12345, 0), (0, 0)]):
            with self.assertRaises(SystemExit):
                arb.halt(reason="synthetic", exit_status=1)
        kill.assert_any_call(12345, signal.SIGTERM)
        for hook in hooks:
            hook.assert_not_called()
        self.assertEqual(arb.cfg.graceful_timeout, 30)
        self.assertTrue(arb._shutdown_started)

    def test_kill_errors_and_counts_preserve_retirement_state(self):
        arb = self.arbiter()
        arb.WORKERS[12345] = self.fake_worker()
        with patch("os.kill", side_effect=PermissionError(errno.EPERM, "synthetic")):
            with self.assertRaises(PermissionError):
                arb.kill_worker(12345, signal.SIGTERM)
        with patch("os.kill") as kill:
            for sig in (signal.SIGABRT, signal.SIGTERM, signal.SIGKILL):
                arb.kill_worker(12345, sig)
            self.assertEqual(kill.call_count, 3)
        self.assertEqual(arb._stats["workers_killed"], 2)
        self.assertIn(12345, arb.WORKERS)
        with self.assertRaises(HaltServer):
            arb.kill_worker(99999, signal.SIGTERM)

    def test_original_timeout_aborts_then_kills_without_early_replacement(self):
        arb = self.arbiter()
        worker = self.fake_worker(last_update=0)
        arb.WORKERS[12345] = worker
        with patch("gunicorn.arbiter.time.monotonic", return_value=31), patch("os.kill") as kill:
            arb.murder_workers()
            self.assertTrue(worker.aborted)
            arb.murder_workers()
        self.assertEqual([call.args for call in kill.call_args_list],
                         [(12345, signal.SIGABRT), (12345, signal.SIGKILL)])
        with patch.object(Arbiter, "spawn_worker", side_effect=forbidden):
            arb.manage_workers()

    def test_healthy_heartbeat_never_killed(self):
        arb = self.arbiter()
        arb.WORKERS[12345] = self.fake_worker(last_update=30)
        with patch("gunicorn.arbiter.time.monotonic", return_value=31):
            arb.murder_workers()
        self.assertFalse(arb.WORKERS[12345].aborted)

    def test_original_unreadable_heartbeat_limitation_is_not_hidden(self):
        arb = self.arbiter()
        worker = self.fake_worker()
        worker.tmp.last_update.side_effect = OSError("synthetic")
        arb.WORKERS[12345] = worker
        arb.murder_workers()
        self.assertFalse(worker.aborted)

    def test_stop_prevents_future_spawn_even_if_final_reap_incomplete(self):
        arb = self.arbiter()
        worker = self.fake_worker()
        arb.WORKERS[12345] = worker
        with patch("gunicorn.arbiter.sock.close_sockets"), patch("os.kill") as kill, \
                patch("gunicorn.arbiter.time.time", side_effect=[0, 31]), \
                patch("os.waitpid", return_value=(0, 0)):
            arb.stop()
        self.assertEqual([call.args for call in kill.call_args_list],
                         [(12345, signal.SIGTERM), (12345, signal.SIGKILL)])
        self.assertIn(12345, arb.WORKERS)
        with self.assertRaises(HaltServer):
            arb.manage_workers()

    def test_original_core_methods_remain_pinned_upstream(self):
        for method in ("run", "murder_workers", "handle_term",
                       "handle_int", "handle_quit", "handle_chld", "handle_cld"):
            self.assertIs(getattr(StagingSingleWorkerArbiter, method), getattr(Arbiter, method))


if __name__ == "__main__":
    unittest.main(verbosity=2)

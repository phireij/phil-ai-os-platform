"""Real POSIX process/temporary-file tests plus bounded syscall failure injection."""
import copy
import errno
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import stat
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import staging_durable_admission as a

CTX = mp.get_context("fork")
BINDING = {"endpoint_ref": "test-only-endpoint", "daemon_identity": "test-daemon"}
PHASES = ("before_temp_open", "before_write", "after_write", "before_file_fsync", "after_file_fsync",
          "before_replace", "after_replace", "before_directory_fsync", "after_directory_fsync", "after_durable_commit")


def init(path):
    return a.Session.initialize(path, **BINDING, reconciliation_ref="explicit-test-only-empty-store")


def revision(s):
    return s.snapshot()["revision"]


def reserve(s):
    return s.reserve_generation(revision=revision(s), generation="generation-1", spec_digest="a" * 64,
                                policy_digest="b" * 64, watchdog_ref="test-fixed-watchdog-contract")


def created(s):
    reserve(s)
    s.bind_created(revision=revision(s), full_id="c" * 64)
    s.register_observer(revision=revision(s), observer_ref="observer-1")


def observation(permit, kind, sequence=1):
    return {"kind": kind, "sequence": sequence, "journal_id": permit.journal_id,
            "generation": permit.generation, "spec_digest": permit.spec_digest, "policy_digest": permit.policy_digest,
            "endpoint_ref": permit.daemon_endpoint_ref, "daemon_identity": permit.daemon_identity,
            "full_id": permit.full_id, "attempt_id": permit.attempt_id, "start_revision": permit.revision,
            "observer_ref": permit.observer_ref}


def contender(path, conn):
    try:
        with a.Session.open(path, **BINDING) as s:
            conn.send(("opened", s.snapshot()["state"]))
    except a.Busy:
        conn.send(("busy", None))
    except Exception as exc:
        conn.send((type(exc).__name__, str(exc)))
    finally:
        conn.close()


def holding_owner(path, conn):
    with init(path) as s:
        created(s)
        conn.send("holding")
        conn.recv()


def crash_action(path, action, phase, conn):
    with init(path) as s:
        if action != "reserve":
            reserve(s)
        if action not in {"reserve", "bind"}:
            s.bind_created(revision=revision(s), full_id="c" * 64)
        if action not in {"reserve", "bind", "observer"}:
            s.register_observer(revision=revision(s), observer_ref="observer-1")
        if action in {"observe", "seal", "unknown", "recover"}:
            permit = s.consume_start(revision=revision(s))
            conn.send("one_permit_before_crash")
        def hit(name):
            if name == phase:
                os._exit(71)
        s._checkpoint = hit
        rev = revision(s)
        if action == "reserve":
            reserve(s)
        elif action == "bind":
            s.bind_created(revision=rev, full_id="c" * 64)
        elif action == "observer":
            s.register_observer(revision=rev, observer_ref="observer-1")
        elif action == "start":
            s.consume_start(revision=rev)
            conn.send("returned_permit")
            hit("after_permit_return")
        elif action == "observe":
            s.observe(revision=rev, observation=observation(permit, "EXIT_REPORTED"))
        elif action == "seal":
            s.seal(revision=rev)
        elif action == "unknown":
            s.observe(revision=rev, observation=observation(permit, "START_RESPONSE_LOST"))
        elif action == "recover":
            s.close()
            a.Session._checkpoint = staticmethod(hit)
            a.Session.open(path, **BINDING)
    conn.send("completed")


def crash_init(path, phase):
    def hit(name):
        if name == phase:
            os._exit(72)
    a.Session._checkpoint = staticmethod(hit)
    init(path)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="admission-local-test-")
        self.path = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def open(self):
        return a.Session.open(self.path, **BINDING)

    def contend(self):
        parent, child = CTX.Pipe()
        p = CTX.Process(target=contender, args=(self.path, child))
        p.start()
        child.close()
        self.assertTrue(parent.poll(5), "contender blocked instead of bounded refusal")
        result = parent.recv()
        p.join(5)
        self.assertEqual(p.exitcode, 0)
        parent.close()
        return result


class CoreTests(Base):
    def test_one_durable_permit_and_immutable_binding(self):
        with init(self.path) as s:
            created(s)
            p = s.consume_start(revision=revision(s))
            rec = s.snapshot()
            self.assertTrue(rec["generation"]["start_consumed"])
            self.assertEqual(rec["state"], "START_INTENT")
            self.assertEqual(rec["generation"]["start_revision"], p.revision)
            self.assertEqual(rec["generation"]["full_id"], p.full_id)
            with self.assertRaises(a.Denied):
                s.consume_start(revision=revision(s))
            with self.assertRaises(Exception):
                p.full_id = "d" * 64
            rec["generation"]["start_consumed"] = False
            self.assertTrue(s.snapshot()["generation"]["start_consumed"])
            with self.assertRaises(a.Denied):
                s.bind_created(revision=revision(s), full_id="d" * 64)
        with self.open() as recovered:
            self.assertEqual(recovered.snapshot()["state"], "UNKNOWN")
            with self.assertRaises(a.Denied):
                recovered.consume_start(revision=revision(recovered))
        with self.open() as again:
            self.assertEqual(again.snapshot()["state"], "UNKNOWN")
            self.assertEqual(again.snapshot()["generation"]["attempt_id"], p.attempt_id)

    def test_reentrant_operations_denied_at_each_persistence_phase(self):
        for phase in PHASES + ("before_permit_return",):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as path, init(path) as s:
                created(s)
                rev = revision(s)
                denied = []
                def nested(name):
                    if name == phase:
                        for operation in (lambda: s.consume_start(revision=rev), s.snapshot, s.close,
                                          lambda: s.seal(revision=rev)):
                            try:
                                operation()
                            except a.Denied:
                                denied.append(True)
                            else:
                                self.fail("nested public operation unexpectedly succeeded")
                s._checkpoint = nested
                p = s.consume_start(revision=rev)
                self.assertEqual(len(denied), 4)
                self.assertEqual(s.snapshot()["generation"]["attempt_id"], p.attempt_id)
                self.assertFalse(s._active_operation)
                with self.assertRaises(a.Denied):
                    s.consume_start(revision=revision(s))

    def test_real_signal_handler_cannot_reenter_start_or_close(self):
        with init(self.path) as s:
            created(s)
            rev = revision(s)
            denied = []
            previous = signal.getsignal(signal.SIGUSR1)
            def handler(signum, frame):
                for operation in (lambda: s.consume_start(revision=rev), s.close, s.snapshot):
                    try:
                        operation()
                    except a.Denied:
                        denied.append(True)
                    else:
                        self.fail("signal handler bypassed operation guard")
            signal.signal(signal.SIGUSR1, handler)
            try:
                def checkpoint(phase):
                    if phase == "after_file_fsync":
                        os.kill(os.getpid(), signal.SIGUSR1)
                s._checkpoint = checkpoint
                p = s.consume_start(revision=rev)
                self.assertEqual(len(denied), 3)
                self.assertEqual(s.snapshot()["generation"]["attempt_id"], p.attempt_id)
                self.assertEqual(self.contend()[0], "busy")
            finally:
                signal.signal(signal.SIGUSR1, previous)

    def test_explicit_initialization_and_missing_state(self):
        with self.assertRaises(a.StorageUnsafe):
            self.open()
        self.assertEqual(os.listdir(self.path), [])
        with init(self.path):
            pass
        with self.assertRaises(a.StorageUnsafe):
            init(self.path)
        os.unlink(Path(self.path) / a.JOURNAL)
        with self.assertRaises(a.StorageUnsafe):
            self.open()
        with self.assertRaises(a.StorageUnsafe):
            init(self.path)

    def test_revision_validation_and_observer_prerequisite(self):
        with init(self.path) as s:
            for invalid in (True, False, -1, 0.0, "0", None):
                with self.subTest(invalid=invalid), self.assertRaises(a.Denied):
                    s.reserve_generation(revision=invalid, generation="g", spec_digest="a" * 64,
                                         policy_digest="b" * 64, watchdog_ref="watchdog")
            reserve(s)
            with self.assertRaises(a.Denied):
                s.bind_created(revision=0, full_id="c" * 64)
            for value in ("abc123", "C" * 64, "c" * 63, "c" * 65, None):
                with self.assertRaises(a.Denied):
                    s.bind_created(revision=revision(s), full_id=value)
            s.bind_created(revision=revision(s), full_id="c" * 64)
            with self.assertRaises(a.Denied):
                s.consume_start(revision=revision(s))

    def test_daemon_change_persists_unknown_original_binding(self):
        with init(self.path):
            pass
        with self.assertRaises(a.Denied):
            a.Session.open(self.path, endpoint_ref=BINDING["endpoint_ref"], daemon_identity="another-daemon")
        with self.open() as s:
            self.assertEqual(s.snapshot()["state"], "UNKNOWN")
            self.assertEqual(s.snapshot()["daemon"]["identity"], "test-daemon")
            with self.assertRaises(a.Denied):
                reserve(s)

    def test_exit_before_ack_terminal_monotonicity(self):
        with init(self.path) as s:
            created(s)
            p = s.consume_start(revision=revision(s))
            first = observation(p, "EXIT_REPORTED")
            s.observe(revision=revision(s), observation=first)
            self.assertEqual(s.snapshot()["state"], "RETIRING")
            rev = revision(s)
            s.observe(revision=rev, observation=first)
            self.assertEqual(revision(s), rev)
            s.observe(revision=revision(s), observation=observation(p, "START_RESPONSE_OK", 2))
            self.assertEqual(s.snapshot()["state"], "RETIRING")
            with self.assertRaises(a.Denied):
                reserve(s)
            s.seal(revision=revision(s))
            self.assertEqual(s.snapshot()["state"], "SEALED")
            s.observe(revision=revision(s), observation=observation(p, "START_RESPONSE_OK", 3))
            self.assertEqual(s.snapshot()["state"], "SEALED")
            s.observe(revision=revision(s), observation=observation(p, "RUNNING_REPORTED", 4))
            self.assertEqual(s.snapshot()["state"], "UNKNOWN")
            self.assertTrue(s.snapshot()["generation"]["sealed"])
        with self.open() as s:
            self.assertTrue(s.snapshot()["generation"]["sealed"])
            with self.assertRaises(a.Denied):
                reserve(s)

    def test_local_seal_never_certifies_or_releases_runtime(self):
        with init(self.path) as s:
            reserve(s)
            s.seal(revision=revision(s))
        with self.open() as s:
            self.assertEqual(s.snapshot()["state"], "SEALED")
            self.assertFalse(hasattr(s, "retire"))
            self.assertFalse(hasattr(s, "release"))
            for operation in (lambda: reserve(s), lambda: s.consume_start(revision=revision(s)),
                              lambda: s.bind_created(revision=revision(s), full_id="c" * 64)):
                with self.assertRaises(a.Denied):
                    operation()

    def test_all_observation_identity_fields_fail_closed(self):
        fields = ("journal_id", "generation", "spec_digest", "policy_digest", "endpoint_ref", "daemon_identity",
                  "full_id", "attempt_id", "start_revision", "observer_ref")
        for field in fields:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as path, init(path) as s:
                created(s)
                p = s.consume_start(revision=revision(s))
                obs = observation(p, "START_RESPONSE_OK")
                obs[field] = 999 if field == "start_revision" else "mismatched"
                s.observe(revision=revision(s), observation=obs)
                self.assertEqual(s.snapshot()["state"], "UNKNOWN")
                s.observe(revision=revision(s), observation=observation(p, "START_RESPONSE_OK"))
                self.assertEqual(s.snapshot()["state"], "UNKNOWN")

    def test_reordered_conflicting_or_lost_observation_is_unknown(self):
        for kind, seq in (("START_RESPONSE_OK", 2), ("START_RESPONSE_ERROR", 1), ("START_RESPONSE_LOST", 1),
                          ("OBSERVER_LOST", 1), ("CONFLICT", 1)):
            with self.subTest(kind=kind, seq=seq), tempfile.TemporaryDirectory() as path, init(path) as s:
                created(s)
                p = s.consume_start(revision=revision(s))
                s.observe(revision=revision(s), observation=observation(p, kind, seq))
                self.assertEqual(s.snapshot()["state"], "UNKNOWN")
        with init(self.path) as s:
            created(s)
            p = s.consume_start(revision=revision(s))
            s.observe(revision=revision(s), observation=observation(p, "START_RESPONSE_OK"))
            self.assertEqual(s.snapshot()["state"], "STARTING")
            s.observe(revision=revision(s), observation=observation(p, "EXIT_REPORTED"))
            self.assertEqual(s.snapshot()["state"], "UNKNOWN")

    def test_arbitrary_evidence_no_retirement_capability(self):
        with init(self.path) as s:
            created(s)
            p = s.consume_start(revision=revision(s))
            for invalid in ({"retired": True}, object(), {**observation(p, "EXIT_REPORTED"), "proof": True},
                            {**observation(p, "EXIT_REPORTED"), "sequence": True}):
                with self.assertRaises(a.Denied):
                    s.observe(revision=revision(s), observation=invalid)
            s.observe(revision=revision(s), observation=observation(p, "EXIT_REPORTED"))
            self.assertEqual(s.snapshot()["state"], "RETIRING")
            self.assertIn("unverified", p.requirements[-1])


class ProcessTests(Base):
    def test_same_process_reentrant_open_and_real_process_contention(self):
        with init(self.path):
            with self.assertRaises(a.Busy):
                self.open()
            self.assertEqual(self.contend()[0], "busy")
        self.assertEqual(self.contend(), ("opened", "CLOSED"))

    def test_stopped_owner_keeps_lock_and_killed_owner_recovers_unknown(self):
        parent, child = CTX.Pipe()
        p = CTX.Process(target=holding_owner, args=(self.path, child))
        p.start()
        child.close()
        try:
            self.assertTrue(parent.poll(5))
            self.assertEqual(parent.recv(), "holding")
            os.kill(p.pid, signal.SIGSTOP)
            waited, status = os.waitpid(p.pid, os.WUNTRACED)
            self.assertEqual(waited, p.pid)
            self.assertTrue(os.WIFSTOPPED(status))
            self.assertEqual(self.contend()[0], "busy")
            self.assertEqual(self.contend()[0], "busy")
            os.kill(p.pid, signal.SIGKILL)
            p.join(5)
            self.assertEqual(p.exitcode, -signal.SIGKILL)
            self.assertEqual(self.contend(), ("opened", "UNKNOWN"))
            self.assertEqual(self.contend(), ("opened", "UNKNOWN"))
        finally:
            if p.is_alive():
                os.kill(p.pid, signal.SIGKILL)
                p.join(5)
            parent.close()

    def test_fork_child_cannot_use_or_unlock_parent_session(self):
        with init(self.path) as s:
            parent, child = CTX.Pipe()
            def inherited():
                try:
                    s.snapshot()
                    child.send("unexpected success")
                except a.Denied:
                    s.close()
                    child.send("denied and closed own fds")
                child.close()
            p = CTX.Process(target=inherited)
            p.start()
            child.close()
            self.assertTrue(parent.poll(5))
            self.assertEqual(parent.recv(), "denied and closed own fds")
            p.join(5)
            self.assertEqual(p.exitcode, 0)
            self.assertEqual(self.contend()[0], "busy")
            self.assertEqual(s.snapshot()["state"], "CLOSED")
            parent.close()

    def test_other_thread_cannot_use_session(self):
        with init(self.path) as s:
            result = []
            def run():
                try:
                    s.snapshot()
                except a.Denied:
                    result.append("denied")
                try:
                    s.close()
                except a.Denied:
                    result.append("close denied")
            t = threading.Thread(target=run)
            t.start()
            t.join(5)
            self.assertEqual(result, ["denied", "close denied"])
            self.assertEqual(self.contend()[0], "busy")

    def test_recycled_thread_identifier_does_not_transfer_ownership(self):
        holder = []
        first = threading.Thread(target=lambda: holder.append(init(self.path)))
        first.start()
        first.join(5)
        s = holder[0]
        results = []
        def second_owner():
            # Force the numeric ident equality that CPython also commonly recycles.
            with mock.patch.object(a.threading, "get_ident", return_value=first.ident):
                for action in (s.snapshot, s.close):
                    try:
                        action()
                    except a.Denied:
                        results.append("denied")
        second = threading.Thread(target=second_owner)
        second.start()
        second.join(5)
        self.assertEqual(results, ["denied", "denied"])
        self.assertEqual(self.contend()[0], "busy")
        # The dead thread has deliberately stranded its lock. Test-only descriptor
        # cleanup, not an exported core release or takeover API.
        os.close(s._lock_fd)
        os.close(s._directory_fd)
        s._closed = True

    def test_foreign_thread_never_clears_active_owner_guard(self):
        with init(self.path) as s:
            created(s)
            rev = revision(s)
            denied = []
            def foreign():
                for action in (s.snapshot, s.close, lambda: s.consume_start(revision=rev)):
                    try:
                        action()
                    except a.Denied:
                        denied.append(True)
            def checkpoint(phase):
                if phase == "after_file_fsync":
                    t = threading.Thread(target=foreign)
                    t.start()
                    t.join(5)
                    self.assertFalse(t.is_alive())
                    self.assertTrue(s._active_operation)
                    with self.assertRaises(a.Denied):
                        s.consume_start(revision=rev)
            s._checkpoint = checkpoint
            p = s.consume_start(revision=rev)
            self.assertEqual(len(denied), 3)
            self.assertEqual(s.snapshot()["generation"]["attempt_id"], p.attempt_id)

    def test_real_crashes_at_every_persistence_boundary_every_transition(self):
        for action in ("reserve", "bind", "observer", "start", "observe", "seal", "unknown", "recover"):
            for phase in PHASES + (("before_permit_return", "after_permit_return") if action == "start" else ()):
                with self.subTest(action=action, phase=phase), tempfile.TemporaryDirectory() as path:
                    parent, child = CTX.Pipe()
                    p = CTX.Process(target=crash_action, args=(path, action, phase, child))
                    p.start()
                    child.close()
                    p.join(5)
                    if p.is_alive():
                        p.kill()
                        p.join()
                        self.fail("crash test stalled")
                    self.assertEqual(p.exitcode, 71)
                    messages = []
                    while parent.poll():
                        try:
                            messages.append(parent.recv())
                        except EOFError:
                            break
                    parent.close()
                    if phase == "after_permit_return":
                        self.assertEqual(messages.count("returned_permit"), 1)
                    else:
                        self.assertNotIn("returned_permit", messages)
                    with a.Session.open(path, **BINDING) as s:
                        rec = s.snapshot()
                        if rec["generation"] is not None:
                            self.assertIn(rec["state"], {"UNKNOWN", "SEALED"})
                            with self.assertRaises(a.Denied):
                                s.consume_start(revision=revision(s))
                            with self.assertRaises(a.Denied):
                                reserve(s)
                        else:
                            self.assertEqual(action, "reserve")
                            self.assertEqual(rec["state"], "CLOSED")

    def test_crashes_during_initialization_never_silent_reinitialize(self):
        for phase in ("init_before_lock_fsync", "init_after_lock_fsync", "init_after_directory_fsync") + PHASES:
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as path:
                p = CTX.Process(target=crash_init, args=(path, phase))
                p.start()
                p.join(5)
                self.assertEqual(p.exitcode, 72)
                with self.assertRaises(a.StorageUnsafe):
                    init(path)
                try:
                    s = a.Session.open(path, **BINDING)
                except (a.AdmissionError, FileNotFoundError):
                    pass
                else:
                    self.assertEqual(s.snapshot()["state"], "CLOSED")
                    s.close()


class StorageTests(Base):
    def mutate_record(self, callback):
        path = Path(self.path) / a.JOURNAL
        env = json.loads(path.read_text())
        callback(env["record"])
        env["sha256"] = hashlib.sha256(a._canonical(env["record"])).hexdigest()
        path.write_bytes(a._canonical(env))

    def test_corrupt_malformed_truncated_and_duplicate_json(self):
        with init(self.path):
            pass
        path = Path(self.path) / a.JOURNAL
        good = path.read_bytes()
        for payload in (b"", good[:20], b"null", b"[]", good + b"garbage", b'{"record":NaN,"sha256":"x"}',
                        b'{"record":{},"record":{},"sha256":"x"}', b"x" * (a.MAX_BYTES + 1),
                        good.replace(b'"CLOSED"', b'"CREATED"'), b'[' * 2000 + b']' * 2000):
            with self.subTest(length=len(payload)):
                path.write_bytes(payload)
                with self.assertRaises(a.StorageUnsafe):
                    self.open()
        path.write_bytes(good)
        with self.open() as s:
            self.assertEqual(s.snapshot()["state"], "CLOSED")

    def test_checksummed_but_inconsistent_schema_rejected(self):
        with init(self.path):
            pass
        path = Path(self.path) / a.JOURNAL
        good = path.read_bytes()
        mutations = (lambda r: r.update(revision=True), lambda r: r.update(schema=1.0),
                     lambda r: r.update(extra="not allowed"), lambda r: r.update(state="START_INTENT"),
                     lambda r: r.update(lock_identity=[0, 0]), lambda r: r.update(directory_identity=[0, 0]))
        for change in mutations:
            path.write_bytes(good)
            self.mutate_record(change)
            with self.assertRaises(a.StorageUnsafe):
                self.open()

    def test_symlinks_hardlinks_and_special_files_rejected(self):
        with init(self.path):
            pass
        journal = Path(self.path) / a.JOURNAL
        original = journal.read_bytes()
        for which in (a.LOCK, a.JOURNAL):
            target = Path(self.path) / which
            saved = target.with_suffix(".saved")
            target.rename(saved)
            target.symlink_to(saved)
            with self.assertRaises((OSError, a.StorageUnsafe)):
                self.open()
            target.unlink()
            saved.rename(target)
            alias = Path(self.path) / "hardlink"
            os.link(target, alias)
            with self.assertRaises(a.StorageUnsafe):
                self.open()
            alias.unlink()
        journal.unlink()
        os.mkfifo(journal)
        with self.assertRaises(a.StorageUnsafe):
            self.open()
        journal.unlink()
        journal.write_bytes(original)
        with tempfile.TemporaryDirectory() as other:
            link = Path(other) / "linked-state"
            link.symlink_to(self.path)
            with self.assertRaises(a.StorageUnsafe):
                a.Session.open(str(link), **BINDING)

    def test_lock_inode_replacement_refused_current_and_successor(self):
        with init(self.path) as s:
            lock = Path(self.path) / a.LOCK
            contents = lock.read_bytes()
            lock.rename(lock.with_suffix(".previous"))
            lock.write_bytes(contents)
            with self.assertRaises(a.StorageUnsafe):
                s.snapshot()
            with self.assertRaises(a.StorageUnsafe):
                self.open()

    def test_directory_replacement_refused(self):
        with tempfile.TemporaryDirectory() as parent:
            path = Path(parent) / "state"
            path.mkdir(mode=0o700)
            with init(str(path)) as s:
                path.rename(Path(parent) / "old")
                path.mkdir(mode=0o700)
                with self.assertRaises(a.StorageUnsafe):
                    s.snapshot()

    def test_external_journal_rollback_poisoned_in_live_session(self):
        with init(self.path) as s:
            journal = Path(self.path) / a.JOURNAL
            old = journal.read_bytes()
            reserve(s)
            journal.write_bytes(old)
            with self.assertRaises(a.StorageUnsafe):
                s.snapshot()
            with self.assertRaises(a.StorageUnsafe):
                reserve(s)

    def test_write_enospc_rename_and_both_fsync_failures_no_permit(self):
        for syscall in ("write", "replace", "file_fsync", "directory_fsync"):
            with self.subTest(syscall=syscall), tempfile.TemporaryDirectory() as path:
                with init(path) as s:
                    created(s)
                    real_fsync = os.fsync
                    def fail_fsync(fd):
                        is_dir = stat.S_ISDIR(os.fstat(fd).st_mode)
                        if is_dir == (syscall == "directory_fsync"):
                            raise OSError(errno.EIO, "injected fsync failure")
                        return real_fsync(fd)
                    name = "fsync" if "fsync" in syscall else syscall
                    effect = fail_fsync if name == "fsync" else OSError(errno.ENOSPC if name == "write" else errno.EIO,
                                                                          "injected storage failure")
                    rev = revision(s)
                    with mock.patch.object(a.os, name, side_effect=effect):
                        with self.assertRaises(a.StorageUnsafe):
                            s.consume_start(revision=rev)
                    with self.assertRaises(a.StorageUnsafe):
                        s.consume_start(revision=rev)
                with a.Session.open(path, **BINDING) as s:
                    self.assertEqual(s.snapshot()["state"], "UNKNOWN")
                    with self.assertRaises(a.Denied):
                        s.consume_start(revision=revision(s))

    def test_exception_after_durable_commit_and_before_return_poisoned(self):
        for phase in ("after_directory_fsync", "after_durable_commit", "before_permit_return"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as path:
                with init(path) as s:
                    created(s)
                    def fail(name):
                        if name == phase:
                            raise OSError(errno.EIO, "injected postcommit uncertainty")
                    s._checkpoint = fail
                    with self.assertRaises(a.StorageUnsafe):
                        s.consume_start(revision=revision(s))
                    with self.assertRaises(a.StorageUnsafe):
                        s.snapshot()
                with a.Session.open(path, **BINDING) as s:
                    self.assertEqual(s.snapshot()["state"], "UNKNOWN")
                    self.assertTrue(s.snapshot()["generation"]["start_consumed"])

    def test_recovery_fsync_failure_remains_blocked_until_durable_unknown(self):
        with init(self.path) as s:
            created(s)
            s.consume_start(revision=revision(s))
        with mock.patch.object(a.os, "fsync", side_effect=OSError(errno.EIO, "unavailable storage")):
            with self.assertRaises(a.StorageUnsafe):
                self.open()
        with self.open() as s:
            self.assertEqual(s.snapshot()["state"], "UNKNOWN")

    def test_short_reads_trailing_bytes_and_early_eof_fail_closed(self):
        with init(self.path) as s:
            real_read = os.read
            def short(fd, count):
                return real_read(fd, min(count, 7))
            with mock.patch.object(a.os, "read", side_effect=short):
                self.assertEqual(s.snapshot()["state"], "CLOSED")
            with mock.patch.object(a.os, "read", return_value=b""):
                with self.assertRaises(a.StorageUnsafe):
                    s.snapshot()
        journal = Path(self.path) / a.JOURNAL
        good = journal.read_bytes()
        journal.write_bytes(good + b" invalid trailing bytes")
        def valid_prefix(fd, count):
            # Simulate a first short read exactly ending at an otherwise valid envelope.
            if os.lseek(fd, 0, os.SEEK_CUR) == 0:
                return real_read(fd, min(len(good), count))
            return real_read(fd, count)
        with mock.patch.object(a.os, "read", side_effect=valid_prefix):
            with self.assertRaises(a.StorageUnsafe):
                self.open()

    def test_partial_initial_lock_write_and_zero_write_failure(self):
        real_write = os.write
        with mock.patch.object(a.os, "write", side_effect=lambda fd, data: real_write(fd, data[:3])):
            with init(self.path) as s:
                self.assertEqual(s.snapshot()["state"], "CLOSED")
        with tempfile.TemporaryDirectory() as path:
            with mock.patch.object(a.os, "write", return_value=0):
                with self.assertRaises(a.StorageUnsafe):
                    init(path)
            with self.assertRaises(a.StorageUnsafe):
                init(path)

    def test_public_storage_errors_are_redacted(self):
        import traceback
        with init(self.path) as s:
            created(s)
            with mock.patch.object(a.os, "fsync", side_effect=OSError(errno.EIO, "SECRET /private/path")):
                try:
                    s.consume_start(revision=revision(s))
                except a.StorageUnsafe as exc:
                    formatted = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                    self.assertNotIn("SECRET", str(exc))
                    self.assertNotIn("SECRET", formatted)
                    self.assertTrue(exc.__suppress_context__)
                else:
                    self.fail("expected redacted storage failure")
        with self.assertRaises(a.StorageUnsafe) as caught:
            a.Session.open("/a-nonexistent-private-path", **BINDING)
        self.assertNotIn("a-nonexistent-private-path", str(caught.exception))

    def test_ambiguous_close_never_retries_reused_descriptors(self):
        s = init(self.path)
        original_lock, original_dir = s._lock_fd, s._directory_fd
        real_close = os.close
        attempted = []
        def ambiguous_close(fd):
            attempted.append(fd)
            real_close(fd)
            if fd == original_dir:
                raise OSError(errno.EIO, "close outcome ambiguous")
        with mock.patch.object(a.os, "close", side_effect=ambiguous_close):
            with self.assertRaises(a.StorageUnsafe):
                s.close()
        self.assertEqual(attempted, [original_lock, original_dir])
        self.assertTrue(s._closed)
        self.assertIsNone(s._lock_fd)
        with self.open() as successor:
            s.close()
            self.assertEqual(successor.snapshot()["state"], "CLOSED")

    def test_short_and_zero_writes(self):
        with init(self.path) as s:
            created(s)
            real_write = os.write
            def short(fd, data):
                return real_write(fd, data[:7])
            with mock.patch.object(a.os, "write", side_effect=short):
                s.consume_start(revision=revision(s))
            self.assertTrue(s.snapshot()["generation"]["start_consumed"])
        with tempfile.TemporaryDirectory() as path, init(path) as s:
            created(s)
            with mock.patch.object(a.os, "write", return_value=0):
                with self.assertRaises(a.StorageUnsafe):
                    s.consume_start(revision=revision(s))


if __name__ == "__main__":
    unittest.main(verbosity=2)

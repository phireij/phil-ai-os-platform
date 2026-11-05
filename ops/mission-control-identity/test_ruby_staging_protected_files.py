"""Synthetic filesystem/JSON tests; never open the real /run/secrets.

The root open is redirected to an owned temporary tree. Directory/file opens,
O_NOFOLLOW/O_NONBLOCK, reads, fstat and close use actual local descriptors.
Read-only mount flags are deliberately simulated: no mount or host change is
performed, and these tests do not prove runtime mount or namespace protection.
"""
from contextlib import contextmanager
from dataclasses import asdict, replace
import inspect
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import patch

DENIED = []
PHASE = "imports"
def audit(event, args):
    if (event.startswith("socket.") and event != "socket.gethostname") or event in {
            "os.system", "os.exec", "os.posix_spawn", "subprocess.Popen"}:
        DENIED.append((event, PHASE))
        raise RuntimeError("protected_files_test_action_denied:" + event)
sys.addaudithook(audit)
os.environ.clear()
sys.dont_write_bytecode = True

import requests
import test_ruby_staging_http_app as support
import ruby_staging_protected_files as loader
from ruby_staging_protected_files import (
    StagingFileOwnership, StagingProtectedConfigurationError,
    create_staging_application_from_files,
)
PHASE = "tests"

_REAL_OPEN, _REAL_CLOSE, _REAL_READ, _REAL_STAT = os.open, os.close, os.read, os.fstat
_REAL_INHERITABLE = os.get_inheritable
GENERATION = "a1" * 16
ERROR = "staging_protected_configuration_invalid"


class ProtectedFilesTests(support.HTTPApplicationTests):
    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "root"
        self.leaf = self.root / "run/secrets/ruby-staging"
        self.leaf.mkdir(parents=True)
        self.config = {"version": 1, "generation": GENERATION, "config": asdict(support.CONFIG),
                       "limits": asdict(support.LIMITS), "max_cache_seconds": 300}
        self.secret = {"version": 1, "generation": GENERATION, "client_secret": support.fixtures.SECRET}
        for p in (self.root, self.root / "run", self.root / "run/secrets"):
            p.chmod(0o755)
        self.write("config.json", json.dumps(self.config).encode())
        self.write("secret.json", json.dumps(self.secret).encode())
        self.leaf.chmod(0o555)
        self.ownership = StagingFileOwnership(os.geteuid(), os.getegid(), os.geteuid(), os.getegid())
        self.live, self.opens, self.reads, self.closed = {}, [], [], []
        self.stat_hook = self.read_hook = self.close_hook = self.vfs_hook = None
        self.inheritable_hook = None
        self.stat_count, self.vfs_count = {}, {}
        self.addCleanup(self.cleanup_tree)

    def cleanup_tree(self):
        for p in sorted(self.root.rglob("*"), reverse=True):
            if p.is_dir() and not p.is_symlink():
                p.chmod(0o755)
        if self.root.exists():self.root.chmod(0o755)
        self.temp.cleanup()

    def write(self, name, data):
        self.leaf.chmod(0o755)
        p = self.leaf / name
        if p.exists():p.chmod(0o600)
        p.write_bytes(data)
        p.chmod(0o400)
        self.leaf.chmod(0o555)

    def raw_stat(self, fd):
        value = _REAL_STAT(fd)
        fields = {name: getattr(value, name) for name in (
            "st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink",
            "st_size", "st_mtime_ns", "st_ctime_ns")}
        role = self.live[fd]
        self.stat_count[role] = self.stat_count.get(role, 0) + 1
        if self.stat_hook:self.stat_hook(role, fields, self.stat_count[role])
        return SimpleNamespace(**fields)

    def open_fd(self, name, flags, *, dir_fd=None):
        if name == "/":
            self.assertIsNone(dir_fd)
            actual = str(self.root)
            role = "/"
        else:
            self.assertIn(dir_fd, self.live)
            self.assertIn(name, ("run", "secrets", "ruby-staging", "config.json", "secret.json"))
            self.assertNotIn("/", name)
            actual = name
            role = name
        self.assertTrue(flags & os.O_NOFOLLOW)
        self.assertTrue(flags & os.O_CLOEXEC)
        self.assertEqual(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC), 0)
        if role.endswith(".json"):
            self.assertTrue(flags & os.O_NONBLOCK)
        else:
            self.assertTrue(flags & os.O_DIRECTORY)
        fd = _REAL_OPEN(actual, flags, **({"dir_fd": dir_fd} if dir_fd is not None else {}))
        self.live[fd] = role
        self.opens.append((role, fd, flags))
        return fd

    def close_fd(self, fd):
        role = self.live.pop(fd)
        _REAL_CLOSE(fd)
        self.closed.append((role, fd))
        if self.close_hook:self.close_hook(role)

    def read_fd(self, fd, size):
        role = self.live[fd]
        self.assertIn(role, ("config.json", "secret.json"))
        self.assertGreater(size, 0)
        self.assertLessEqual(size, 4096)
        self.reads.append((role, size))
        if self.read_hook:self.read_hook(role, fd)
        return _REAL_READ(fd, size)

    def vfs(self, fd):
        role = self.live[fd]
        self.vfs_count[role] = self.vfs_count.get(role, 0) + 1
        flags = os.ST_RDONLY
        if self.vfs_hook:flags = self.vfs_hook(role, self.vfs_count[role])
        return SimpleNamespace(f_flag=flags)

    def inheritable(self, fd):
        if self.inheritable_hook:return self.inheritable_hook(self.live[fd])
        return _REAL_INHERITABLE(fd)

    @contextmanager
    def filesystem(self):
        # Redirect only the loader's root acquisition. No actual system root,
        # /run/secrets, device or external credential is opened.
        with patch.object(loader.os, "open", side_effect=self.open_fd), \
             patch.object(loader.os, "close", side_effect=self.close_fd), \
             patch.object(loader.os, "read", side_effect=self.read_fd), \
             patch.object(loader.os, "fstat", side_effect=self.raw_stat), \
             patch.object(loader.os, "fstatvfs", side_effect=self.vfs), \
             patch.object(loader.os, "get_inheritable", side_effect=self.inheritable):
            try:yield
            finally:self.assertEqual(self.live, {}, "owned file descriptor leak")

    def options(self, **changes):
        opts = dict(enabled=True, ownership=self.ownership, expected_generation=GENERATION,
                    wall_clock=lambda:self.wall, monotonic_clock=lambda:self.mono)
        opts.update(changes)
        return opts

    def invoke(self, **changes):
        with self.filesystem():
            app = create_staging_application_from_files(**self.options(**changes))
        self.apps.append(app)
        return app

    def reject(self, **changes):
        with patch.object(requests, "Session") as session:
            with self.assertRaisesRegex(StagingProtectedConfigurationError, "^" + ERROR + "$"):
                self.invoke(**changes)
            session.assert_not_called()
        self.assertEqual(self.live, {})

    def test_disabled_reads_no_inputs_identity_or_files(self):
        class Poison:
            def __getattribute__(self, name):raise AssertionError("disabled_input_inspected")
        poison = Poison()
        with patch.object(loader.os, "open") as opened, patch.object(loader.os, "geteuid") as uid, \
             patch.object(loader.os, "getegid") as gid, patch.object(requests, "Session") as session:
            app = create_staging_application_from_files(ownership=poison, expected_generation=poison,
                wall_clock=poison, monotonic_clock=poison)
            self.apps.append(app)
            self.assertEqual(self.call(app)[0], 503)
            for call in (opened, uid, gid, session):call.assert_not_called()

    def test_invalid_enable_policy_generation_and_clocks_do_not_open(self):
        changes = [{"enabled":x} for x in (None, 0, 1, "true")]
        changes += [{"ownership":x} for x in (None, {}, object())]
        changes += [{"expected_generation":x} for x in (None, "", "A"*32, "a"*31, "a"*33, 1)]
        changes += [{"wall_clock":None}, {"monotonic_clock":None}]
        for change in changes:
            with self.subTest(change=change):self.reject(**change)
        self.assertEqual(self.opens, [])

    def test_invalid_ownership_including_root_reader_fails_before_open(self):
        for field in ("reader_uid", "reader_gid", "directory_uid", "directory_gid"):
            for value in (True, -1, 2**32-1, "1000", None):
                with self.subTest(field=field,value=value):self.reject(ownership=replace(self.ownership, **{field:value}))
        self.reject(ownership=replace(self.ownership, reader_uid=0))
        self.assertEqual(self.opens, [])

    def test_effective_identity_must_match_explicit_policy(self):
        self.reject(ownership=replace(self.ownership, reader_uid=self.ownership.reader_uid+1))
        self.reject(ownership=replace(self.ownership, reader_gid=self.ownership.reader_gid+1))
        self.assertEqual(self.opens, [])

    def test_unsupported_required_flag_rejected_without_open(self):
        for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK", "ST_RDONLY"):
            with self.subTest(name=name), patch.object(loader.os, name, 0):self.reject()
        self.assertEqual(self.opens, [])

    def test_exact_snapshot_transferred_after_all_descriptors_closed(self):
        marker = object()
        def constructed(**kwargs):
            self.assertEqual(self.live, {})
            self.assertEqual(len(self.closed), 6)
            self.assertEqual(kwargs["config"], support.CONFIG)
            self.assertEqual(kwargs["limits"], support.LIMITS)
            self.assertEqual(kwargs["client_secret"], support.fixtures.SECRET)
            self.assertEqual(kwargs["max_cache_seconds"], 300)
            return marker
        with self.filesystem(), patch.object(loader, "create_staging_application", side_effect=constructed):
            self.assertIs(create_staging_application_from_files(**self.options()), marker)
        self.assertEqual([p for p,_,_ in self.opens], ["/","run","secrets","ruby-staging","config.json","secret.json"])
        self.assertEqual([p for p,_ in self.closed], ["secret.json","config.json","ruby-staging","secrets","run","/"])

    def test_real_factory_signed_login_read_and_logout(self):
        app=self.invoke();session,_,_,_=self.login(app)
        self.assertEqual(self.call(app,"/api/ruby-review-synthetic",cookie=session)[0],200)
        status,_,body=self.call(app,"/api/session",cookie=session)
        self.assertEqual(status,200)
        self.assertEqual(self.call(app,"/auth/logout",method="POST",cookie=session,
            HTTP_ORIGIN=support.ORIGIN,HTTP_X_CSRF_TOKEN=json.loads(body)["csrf_token"])[0],200)
        self.assertEqual(self.call(app,"/api/session",cookie=session)[0],401)

    def test_ancestor_symlinks_rejected_by_real_open(self):
        for component in ("run", "secrets", "ruby-staging"):
            with self.subTest(component=component):
                target={"run":self.root/"run", "secrets":self.root/"run/secrets", "ruby-staging":self.leaf}[component]
                backup=target.with_name(target.name+"-real")
                target.rename(backup);target.symlink_to(backup.name,target_is_directory=True)
                try:self.reject()
                finally:target.unlink();backup.rename(target)
        self.assertEqual(self.reads, [])

    def test_file_symlink_and_broken_symlink_rejected(self):
        for name in ("config.json","secret.json"):
            for target in ("other-real.json","absent.json"):
                with self.subTest(name=name,target=target):
                    if target=="other-real.json":
                        self.write(target,(self.leaf/name).read_bytes())
                    self.leaf.chmod(0o755);p=self.leaf/name;backup=self.leaf/(name+".old")
                    p.rename(backup);p.symlink_to(target);self.leaf.chmod(0o555)
                    try:self.reject()
                    finally:
                        self.leaf.chmod(0o755);p.unlink();backup.rename(p)
                        if target=="other-real.json":(self.leaf/target).unlink()
                        self.leaf.chmod(0o555)
        self.assertEqual(self.reads, [])

    def test_fifo_rejected_before_any_read_without_hanging(self):
        self.leaf.chmod(0o755);p=self.leaf/"secret.json";p.unlink();os.mkfifo(p,0o400);self.leaf.chmod(0o555)
        self.reject();self.assertEqual(self.reads, [])

    def test_hard_link_rejected_before_read(self):
        self.leaf.chmod(0o755);os.link(self.leaf/"secret.json",self.leaf/"another-secret");self.leaf.chmod(0o555)
        self.reject();self.assertEqual(self.reads, [])

    def test_file_metadata_mismatches_rejected_before_read(self):
        for field,value in (("st_uid",self.ownership.reader_uid+1),("st_gid",self.ownership.reader_gid+1),
                            ("st_mode",stat.S_IFREG|0o600),("st_mode",stat.S_IFREG|0o440),
                            ("st_mode",stat.S_IFREG|0o4400),("st_mode",stat.S_IFCHR|0o400),
                            ("st_nlink",0),("st_nlink",2),("st_size",0),("st_size",8193)):
            with self.subTest(field=field,value=value):
                self.stat_hook=lambda role,d,n,field=field,value=value:d.update({field:value}) if role=="secret.json" else None
                self.reject()
        self.assertEqual(self.reads, [])

    def test_directory_metadata_policy_rejected_before_read(self):
        for field,value in (("st_uid",self.ownership.directory_uid+1),("st_gid",self.ownership.directory_gid+1),
                            ("st_mode",stat.S_IFDIR|0o777),("st_mode",stat.S_IFDIR|0o2755),
                            ("st_mode",stat.S_IFREG|0o755)):
            with self.subTest(field=field,value=value):
                self.stat_hook=lambda role,d,n,field=field,value=value:d.update({field:value}) if role=="run" else None
                self.reject()
        self.assertEqual(self.reads, [])

    def test_leaf_exact_mode_and_readonly_view_required(self):
        self.leaf.chmod(0o755);self.reject();self.leaf.chmod(0o555)
        for role in ("ruby-staging","config.json","secret.json"):
            with self.subTest(role=role):
                self.vfs_hook=lambda current,n,role=role:0 if current==role else os.ST_RDONLY
                self.reject()
        self.assertEqual(self.reads, [])

    def test_inheritable_descriptor_rejected(self):
        for role in ("/","config.json","secret.json"):
            with self.subTest(role=role):
                self.inheritable_hook=lambda current,role=role:current==role
                self.reject()
        self.assertEqual(self.reads, [])

    def test_metadata_or_mount_change_after_read_rejected(self):
        for field,value in (("st_ino",0),("st_uid",0),("st_mode",stat.S_IFREG|0o600),
                            ("st_size",1),("st_mtime_ns",0),("st_ctime_ns",0)):
            with self.subTest(field=field):
                self.stat_count={};self.stat_hook=lambda role,d,n,field=field,value=value:d.update({field:value}) if role=="secret.json" and n==2 else None
                self.reject()
        self.stat_hook=None;self.vfs_count={}
        self.vfs_hook=lambda role,n:0 if role=="secret.json" and n==2 else os.ST_RDONLY
        self.reject()

    def test_actual_same_length_file_change_detected(self):
        done=[]
        def change(role,fd):
            if role=="config.json" and not done:
                done.append(True)
                self.write("secret.json",json.dumps({**self.secret,"client_secret":"X"*len(support.fixtures.SECRET)}).encode())
        self.read_hook=change
        self.reject()

    def test_short_or_growing_read_rejected(self):
        with self.filesystem(), patch.object(loader.os,"read",return_value=b""):
            with self.assertRaisesRegex(StagingProtectedConfigurationError,ERROR):
                create_staging_application_from_files(**self.options())
        with self.filesystem(), patch.object(loader.os,"read",side_effect=lambda fd,n:b"x"*n) as reads:
            with self.assertRaisesRegex(StagingProtectedConfigurationError,ERROR):
                create_staging_application_from_files(**self.options())
            self.assertLessEqual(reads.call_count,5)

    def test_json_encoding_duplicates_unknown_fields_and_types_rejected(self):
        raw_cases=[b'\xff',b'\xef\xbb\xbf{}',b'[]',b'{',b'{"version":1,"version":1}',
                   json.dumps({**self.config,"extra":True}).encode(),
                   json.dumps({**self.config,"version":True}).encode(),
                   json.dumps({**self.config,"config":[]}).encode(),
                   json.dumps({**self.config,"limits":{**self.config['limits'],"unknown":1}}).encode(),
                   json.dumps({**self.config,"max_cache_seconds":float('nan')}).encode()]
        for raw in raw_cases:
            with self.subTest(raw=raw[:35]):self.write("config.json",raw);self.reject()

    def test_generation_mismatch_never_reaches_factory(self):
        for name,value in (("config.json",self.config),("secret.json",self.secret)):
            self.write(name,json.dumps({**value,"generation":"b2"*16}).encode())
            self.reject()
            self.write(name,json.dumps(value).encode())
        self.reject(expected_generation="c3"*16)

    def test_existing_factory_policy_and_secret_checks_remain_enforced(self):
        cases=[("config.json",{**self.config,"config":{**self.config['config'],"origin":support.app_module.PRODUCTION_ORIGIN}}),
               ("config.json",{**self.config,"config":{**self.config['config'],"idle_seconds":999}}),
               ("config.json",{**self.config,"limits":{**self.config['limits'],"max_inflight_requests":True}}),
               ("config.json",{**self.config,"max_cache_seconds":False}),
               ("secret.json",{**self.secret,"client_secret":"bad\nsecret"}),
               ("secret.json",{**self.secret,"client_secret":{"not":"a string"}})]
        for name,value in cases:
            with self.subTest(name=name,value=value):
                self.write(name,json.dumps(value).encode());self.reject()
                self.write(name,json.dumps(self.config if name=="config.json" else self.secret).encode())

    def test_error_and_traceback_do_not_render_secret_or_raw_failure(self):
        with self.filesystem(), patch.object(loader,"create_staging_application",side_effect=RuntimeError(support.fixtures.SECRET)):
            try:create_staging_application_from_files(**self.options())
            except StagingProtectedConfigurationError as exc:
                self.assertEqual(str(exc),ERROR)
                self.assertNotIn(support.fixtures.SECRET,"".join(traceback.format_exception(exc)))
            else:self.fail("expected fixed error")

    def test_control_failure_preserved_after_all_closes(self):
        failure=KeyboardInterrupt("synthetic-control")
        self.read_hook=lambda role,fd:(_ for _ in ()).throw(failure)
        self.close_hook=lambda role:(_ for _ in ()).throw(SystemExit("synthetic-cleanup"))
        with self.filesystem(), patch.object(loader,"create_staging_application") as construct:
            with self.assertRaises(KeyboardInterrupt) as caught:create_staging_application_from_files(**self.options())
            self.assertIs(caught.exception,failure);construct.assert_not_called()
        self.assertEqual(len(self.closed),6)

    def test_close_failure_prevents_factory_and_other_fds_still_close(self):
        for failure in (OSError("synthetic-close"),SystemExit("synthetic-close-control")):
            self.closed=[]
            self.close_hook=lambda role,failure=failure:(_ for _ in ()).throw(failure) if role=="secret.json" else None
            with self.filesystem(), patch.object(loader,"create_staging_application") as construct:
                with self.assertRaises(StagingProtectedConfigurationError if isinstance(failure,Exception) else SystemExit):
                    create_staging_application_from_files(**self.options())
                construct.assert_not_called()
            self.assertEqual(len(self.closed),6)

    def test_source_has_no_implicit_activation_or_permissions_mutations(self):
        source=inspect.getsource(loader)
        for forbidden in ("os.environ", "os.chmod(", "os.chown(", "os.mkdir(", "serve_forever", "make_server", "requests."):
            self.assertNotIn(forbidden,source)
        signature=inspect.signature(create_staging_application_from_files)
        self.assertIs(signature.parameters['enabled'].default,False)
        self.assertIsNone(signature.parameters['ownership'].default)
        self.assertIsNone(signature.parameters['expected_generation'].default)

    def test_later_control_close_error_outranks_earlier_ordinary_error(self):
        first_control=KeyboardInterrupt("synthetic-first-control")
        def failed_close(role):
            if role=="secret.json":raise OSError("synthetic-ordinary-close")
            if role=="config.json":raise first_control
            if role=="ruby-staging":raise SystemExit("synthetic-later-control")
        self.close_hook=failed_close
        with self.filesystem(), patch.object(loader,"create_staging_application") as construct:
            with self.assertRaises(KeyboardInterrupt) as caught:
                create_staging_application_from_files(**self.options())
            self.assertIs(caught.exception,first_control)
            construct.assert_not_called()
        self.assertEqual(len(self.closed),6)


if __name__ == "__main__":
    names=[name for name in ProtectedFilesTests.__dict__ if name.startswith("test_")]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(ProtectedFilesTests(name) for name in names))
    if DENIED not in ([],[("socket.__new__","imports")]):raise AssertionError("unexpected_protected_files_test_action")
    print("PROTECTED_FILES_TEST_DENIALS="+json.dumps(DENIED))
    raise SystemExit(0 if result.wasSuccessful() else 1)

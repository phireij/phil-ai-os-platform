"""Offline adversarial checks. No activation, certificate issuance, or sockets.

Real descriptor traversal is redirected from '/' into an owned temporary tree.
ST_RDONLY, PID/PPID, and historical time are SIMULATED; this is not evidence of
real mount immutability, a real fork lifecycle, or production certificate trust.
Public expired Gunicorn fixtures are hash checked before copying. SSL key pairing
uses real OpenSSL via /proc/self/fd, without making a connection or listener. MemoryBIO protocol checks use the same
expired public fixture: CERT_NONE is restricted to explicitly synthetic clients.
A separate verified client checks expiry with real OpenSSL time, not the mocked
loader clock. These are not evidence of browser trust or serving readiness.
"""
import contextlib
import dataclasses
import hashlib
import os
from pathlib import Path
import shutil
import ssl
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import ruby_staging_tls_context as m


def deny_network_and_process(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = os.fsdecode(args[0])
        if path == '/' or path == '/run/secrets' or path.startswith('/run/secrets/'):
            raise AssertionError('test forbids live root and secret access')
    if event.startswith('socket.') or event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.fork', 'os.forkpty', 'os.exec', 'os.spawn'}:
        raise AssertionError('test forbids network and subprocess activity')
sys.addaudithook(deny_network_and_process)

if not os.environ.get('RUBY_STAGING_TEST_GUNICORN_SOURCE'):
    raise RuntimeError('RUBY_STAGING_TEST_GUNICORN_SOURCE must name the retained pinned Gunicorn source')
SOURCE = Path(os.environ['RUBY_STAGING_TEST_GUNICORN_SOURCE'])
FIXTURES = {'server.crt': 'cd123363b2626f8b4737a208c71e03af48db091a5bd638cf95ea10dfe13d11f3', 'server.key': '9eca66cac80b52369d9aef35e1203f82c10b724525a11c74ff5838810444b6fd'}
BEGIN = 1770290122
MARKER = 'PRIVATE KEY DO NOT EXPOSE'

class FakeContext:
    def __init__(self, *args):
        self.options = 0
        self.keylog_filename = None
    def set_alpn_protocols(self, value):
        self.alpn = value
    def load_cert_chain(self, cert, key, password):
        self.paths = cert, key
        self.password = password
        cert_fd = int(cert.rsplit('/', 1)[1])
        self.original_cert_offset = os.lseek(cert_fd, 0, os.SEEK_CUR)
        self.cert_size = os.fstat(cert_fd).st_size
        with open(cert, 'rb') as reopened:
            self.reopened_offset = reopened.tell()
            self.pem_header = reopened.readline()
        self.original_offset_after_reopen = os.lseek(cert_fd, 0, os.SEEK_CUR)
        for path in self.paths:
            os.fstat(int(path.rsplit('/', 1)[1]))


class BoundedMemoryTLS:
    """Two SSLObjects only: no sockets, sleeps, external I/O, or unbounded pump."""
    MAX_STEPS = 64
    MAX_BYTES = 256 * 1024

    def __init__(self, server_context, client_context, hostname='localhost'):
        self.client_in, self.client_out = ssl.MemoryBIO(), ssl.MemoryBIO()
        self.server_in, self.server_out = ssl.MemoryBIO(), ssl.MemoryBIO()
        self.client = client_context.wrap_bio(
            self.client_in, self.client_out, server_hostname=hostname)
        self.server = server_context.wrap_bio(
            self.server_in, self.server_out, server_side=True)
        self.transferred = 0
        self.wire = bytearray()
        self.complete = set()
        self.errors = {}

    def pump(self):
        count = 0
        for source, destination in [(self.client_out, self.server_in),
                                    (self.server_out, self.client_in)]:
            pending = source.pending
            if self.transferred + pending > self.MAX_BYTES:
                raise AssertionError('MemoryBIO byte budget exhausted')
            if pending:
                encrypted = source.read(pending)
                self.wire.extend(encrypted)
                self.transferred += len(encrypted)
                count += len(encrypted)
                destination.write(encrypted)
        return count

    def handshake(self):
        for _ in range(self.MAX_STEPS):
            for name in ['client', 'server']:
                if name in self.complete or name in self.errors:
                    continue
                try:
                    getattr(self, name).do_handshake()
                    self.complete.add(name)
                except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                    pass
                except ssl.SSLError as error:
                    self.errors[name] = error
            moved = self.pump()
            if len(self.complete) == 2:
                return
            if self.errors and not moved:
                return
            if not moved and not self.errors:
                raise AssertionError('MemoryBIO handshake stalled')
        raise AssertionError('MemoryBIO handshake step budget exhausted')

    def exchange(self, sender, receiver, payload):
        written = 0
        received = bytearray()
        for _ in range(self.MAX_STEPS):
            if written < len(payload):
                try:
                    written += sender.write(payload[written:])
                except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                    pass
            self.pump()
            try:
                received.extend(receiver.read(len(payload) - len(received)))
            except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                pass
            if len(received) == len(payload):
                return bytes(received)
        raise AssertionError('MemoryBIO application step budget exhausted')


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ruby-tls-test-')
        self.root = Path(self.temp.name)
        self.leaf = self.root / 'run/secrets/ruby-staging-tls'
        self.leaf.mkdir(parents=True)
        for source, target in [('server.crt', 'certificate.pem'), ('server.key', 'private-key.pem')]:
            raw = (SOURCE / 'tests/docker/http2/certs' / source).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), FIXTURES[source])
            (self.leaf / target).write_bytes(raw)
            (self.leaf / target).chmod(0o400)
        for d in [self.root, self.root/'run', self.root/'run/secrets']:
            d.chmod(0o755)
        self.leaf.chmod(0o555)
        self.policy = m.StagingTLSPolicy('a'*32, 'localhost', '7bd0911c79e9fef7631ec045b6a8280cf390bb2a38032cfd4cee9b62f95d97dc', os.getuid(), os.getgid(), os.getuid(), os.getgid(), BEGIN+60, BEGIN+3600, 300)
        self.opened, self.closed = [], []
        self.real_open, self.real_close = os.open, os.close
    def tearDown(self):
        self.leaf.chmod(0o755)
        key = self.leaf/'private-key.pem'
        if key.is_dir(): key.chmod(0o700)
        self.temp.cleanup()
    def preparation(self, policy=None):
        with patch.object(m.os, 'getpid', return_value=101):
            return m.StagingTLSContextPreparation(enabled=True, policy=policy or self.policy)
    @contextlib.contextmanager
    def harness(self, fake=False):
        def opened(path, flags, *args, **kwargs):
            if path == '/':
                path = str(self.root)
            elif os.path.isabs(path):
                raise AssertionError('unexpected absolute open')
            fd = self.real_open(path, flags, *args, **kwargs)
            self.opened.append(fd)
            return fd
        def closed(fd):
            self.closed.append(fd)
            self.real_close(fd)
        with contextlib.ExitStack() as stack:
            for obj, name, value in [(m.os, 'open', opened), (m.os, 'close', closed), (m.os, 'fstatvfs', lambda fd: types.SimpleNamespace(f_flag=os.ST_RDONLY)), (m.os, 'getpid', lambda: 102), (m.os, 'getppid', lambda:101), (m.time, 'time', lambda: BEGIN+120)]:
                stack.enter_context(patch.object(obj,name,value))
            stack.enter_context(patch.dict(os.environ, {}, clear=True))
            if fake:
                stack.enter_context(patch.object(m.ssl, 'SSLContext', FakeContext))
            yield
    def rejected(self, prep=None, env=None):
        with self.assertRaises(m.StagingTLSContextError) as caught:
            (prep or self.preparation()).load(configured_environment={} if env is None else env)
        self.assertEqual(str(caught.exception), 'staging_tls_context_invalid')
        self.assertNotIn(MARKER, str(caught.exception))
    def cleaned(self):
        self.assertEqual(self.closed, list(reversed(self.opened)))
        for fd in self.opened:
            with self.assertRaises(OSError): os.fstat(fd)
    def test_default_off_has_no_file_time_or_ssl_activity(self):
        prep = m.StagingTLSContextPreparation()
        with patch.object(m.os,'open',side_effect=AssertionError), patch.object(m.ssl,'SSLContext',side_effect=AssertionError), patch.object(m.time,'time',side_effect=AssertionError):
            self.assertIsNone(prep.load(configured_environment=None))
            self.assertIsNone(prep.load(configured_environment={'SSLKEYLOGFILE':'x'}))
    def test_enabled_requires_exact_bool_and_policy_type(self):
        for value in [1, None, 'yes']:
            with self.subTest(value=value), self.assertRaises(m.StagingTLSContextError): m.StagingTLSContextPreparation(enabled=value)
        for value in [None, {}, object()]:
            with self.subTest(value=value), self.assertRaises(m.StagingTLSContextError): m.StagingTLSContextPreparation(enabled=True, policy=value)
    def test_policy_invalid_fields(self):
        cases={'generation':['A'*32,'a'*31,None], 'hostname':['LOCALHOST','localhost.','*.localhost','127.0.0.1','a..b','-a','é.test','a'*64], 'certificate_sha256':['A'*64,'0'*63,None], 'reader_uid':[0,True,-1,2**32-1], 'reader_gid':[True,-1], 'directory_uid':[-1], 'directory_gid':[2**32], 'review_start':[True,-1,2**53,BEGIN+3600], 'review_end':[BEGIN+60], 'renewal_margin_seconds':[0,-1,False]}
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field,value=value), self.assertRaises(m.StagingTLSContextError): self.preparation(dataclasses.replace(self.policy, **{field:value}))
    def test_real_context_and_fd_cleanup(self):
        prep=self.preparation()
        with self.harness(): ctx=prep.load(configured_environment={})
        self.assertIsInstance(ctx,ssl.SSLContext)
        self.assertEqual(ctx.minimum_version,ssl.TLSVersion.TLSv1_2)
        self.assertEqual(ctx.maximum_version,ssl.TLSVersion.TLSv1_3)
        self.assertTrue(ctx.options & ssl.OP_NO_TICKET)
        self.assertEqual(ctx.num_tickets,0)
        self.assertIsNone(ctx.keylog_filename)
        self.assertEqual(len(self.opened),6)
        self.cleaned()
        self.assertIsNone(ctx.sni_callback(None,'localhost',ctx))
        for name in [None,'wrong','LOCALHOST','localhost.']:
            self.assertEqual(ctx.sni_callback(None,name,ctx),ssl.ALERT_DESCRIPTION_UNRECOGNIZED_NAME)
        self.assertEqual(ctx.sni_callback(None,'localhost',object()),ssl.ALERT_DESCRIPTION_UNRECOGNIZED_NAME)
        with self.harness(): self.rejected(prep)
    def test_parent_identity_and_keylog_reject_before_open(self):
        for name,value in [('getpid',101),('getppid',999),('geteuid',0),('getegid',999)]:
            prep=self.preparation()
            with self.subTest(name=name), self.harness(), patch.object(m.os,name,return_value=value): self.rejected(prep)
        for env in [{'SSLKEYLOGFILE':''}, {'SSLKEYLOGFILE':'/tmp/no'}, {'OTHER':None}, {'OTHER':1}, {1:'value'}, {None:'value'}, [], None]:
            prep=self.preparation()
            with self.harness():
                with self.assertRaises(m.StagingTLSContextError): prep.load(configured_environment=env)
        prep=self.preparation()
        with self.harness(), patch.dict(os.environ,{'SSLKEYLOGFILE':''}): self.rejected(prep)
        self.assertEqual(self.opened,[])
    def test_clock_window(self):
        for now in [float('nan'),float('inf'),BEGIN+59,BEGIN+3600]:
            prep=self.preparation()
            with self.subTest(now=now), self.harness(), patch.object(m.time,'time',return_value=now): self.rejected(prep)
        self.assertEqual(self.opened,[])
    def test_certificate_policy_exactness(self):
        for changes in [{'certificate_sha256':'0'*64},{'hostname':'other.example'},{'review_start':BEGIN-1},{'review_end':BEGIN+86400-300}]:
            prep=self.preparation(dataclasses.replace(self.policy,**changes))
            with self.subTest(changes=changes),self.harness(): self.rejected(prep)
            self.cleaned(); self.opened.clear();self.closed.clear()
    def test_single_attempt_after_failure(self):
        prep=self.preparation()
        with self.harness():
            self.rejected(prep, {'SSLKEYLOGFILE':''})
            self.rejected(prep)
        self.assertEqual(self.opened,[])
    def test_file_modes(self):
        for mode in [0o600,0o444,0o000,0o401]:
            (self.leaf/'private-key.pem').chmod(mode)
            prep=self.preparation()
            with self.subTest(mode=mode),self.harness(): self.rejected(prep)
            self.cleaned();self.opened.clear();self.closed.clear()
    def test_bad_directory_modes(self):
        for target,mode in [(self.root,0o777),(self.root/'run',0o700),(self.leaf,0o755)]:
            old=stat.S_IMODE(target.stat().st_mode);target.chmod(mode)
            prep=self.preparation()
            with self.subTest(target=str(target)),self.harness(): self.rejected(prep)
            target.chmod(old);self.cleaned();self.opened.clear();self.closed.clear()
    def change_key(self, kind):
        self.leaf.chmod(0o755);key=self.leaf/'private-key.pem';key.unlink()
        if kind=='symlink': key.symlink_to('certificate.pem')
        elif kind=='directory': key.mkdir(mode=0o400)
        elif kind=='fifo': os.mkfifo(key,0o400)
        elif kind=='hardlink': os.link(self.leaf/'certificate.pem',key)
        else: key.write_bytes(b'' if kind=='empty' else b'x'*(m._KEY_MAX+1));key.chmod(0o400)
        self.leaf.chmod(0o555)
    def test_file_shapes(self):
        for kind in ['symlink','fifo','hardlink','empty','oversize','directory']:
            with self.subTest(kind=kind):
                self.change_key(kind);prep=self.preparation()
                with self.harness(): self.rejected(prep)
                self.cleaned();self.opened.clear();self.closed.clear()
    def test_writable_mount_rejected(self):
        prep=self.preparation()
        with self.harness(),patch.object(m.os,'fstatvfs',return_value=types.SimpleNamespace(f_flag=0)): self.rejected(prep)
        self.cleaned()
    def test_descriptor_lifetime_and_password_callback(self):
        prep=self.preparation()
        with self.harness(fake=True): ctx=prep.load(configured_environment={})
        self.assertEqual(ctx.alpn,['http/1.1'])
        self.assertEqual(ctx.original_cert_offset,ctx.cert_size)
        self.assertEqual(ctx.reopened_offset,0)
        self.assertEqual(ctx.pem_header,b'-----BEGIN CERTIFICATE-----\n')
        self.assertEqual(ctx.original_offset_after_reopen,ctx.cert_size)
        self.assertTrue(all(path.startswith('/proc/self/fd/') for path in ctx.paths))
        with self.assertRaises(m.StagingTLSContextError): ctx.password()
        self.cleaned()
    def test_invalid_key_and_private_diagnostic_suppression(self):
        key=self.leaf/'private-key.pem';key.chmod(0o600);key.write_bytes(MARKER.encode());key.chmod(0o400)
        prep=self.preparation()
        with self.harness(): self.rejected(prep)
        self.cleaned()
    def test_certificate_parse_failure(self):
        cert=self.leaf/'certificate.pem';cert.chmod(0o600);cert.write_bytes(MARKER.encode());cert.chmod(0o400)
        prep=self.preparation()
        with self.harness(): self.rejected(prep)
        self.cleaned()
    def test_load_failure_and_control_exceptions_cleanup(self):
        for failure in [ValueError(MARKER),KeyboardInterrupt(),SystemExit(7)]:
            prep=self.preparation()
            with self.harness(fake=True),patch.object(FakeContext,'load_cert_chain',side_effect=failure):
                if isinstance(failure,Exception): self.rejected(prep)
                else:
                    with self.assertRaises(type(failure)) as caught: prep.load(configured_environment={})
                    self.assertIs(caught.exception,failure)
            self.cleaned();self.opened.clear();self.closed.clear()
    def test_close_failure_does_not_skip_other_descriptors(self):
        for failure in [OSError(MARKER),KeyboardInterrupt()]:
            prep=self.preparation()
            def close(fd):
                self.closed.append(fd);self.real_close(fd)
                if len(self.closed)==1: raise failure
            with self.harness(fake=True),patch.object(m.os,'close',close):
                if isinstance(failure,Exception): self.rejected(prep)
                else:
                    with self.assertRaises(KeyboardInterrupt): prep.load(configured_environment={})
            self.cleaned();self.opened.clear();self.closed.clear()
    def test_post_load_mutation_rejected(self):
        key=self.leaf/'private-key.pem'
        def mutate(*args,**kwargs): key.chmod(0o600)
        prep=self.preparation()
        with self.harness(fake=True),patch.object(FakeContext,'load_cert_chain',mutate): self.rejected(prep)
        self.cleaned()
    def test_audit_guard_blocks_live_access_and_sockets(self):
        for path in ['/', '/run/secrets', '/run/secrets/private-key.pem']:
            with self.subTest(path=path), self.assertRaises(AssertionError): self.real_open(path, os.O_RDONLY)
        import socket
        with self.assertRaises(AssertionError): socket.socket()
    def test_directory_symlink_rejected(self):
        self.leaf.chmod(0o755)
        target = self.root/'run/secrets/actual-tls'
        self.leaf.rename(target)
        self.leaf.symlink_to('actual-tls', target_is_directory=True)
        prep=self.preparation()
        with self.harness(): self.rejected(prep)
        self.cleaned()
    def test_bounded_read_short_and_excess(self):
        for chunks in [[b'a', b''], [b'abc'], [b'ab', b'c']]:
            with self.subTest(chunks=chunks),patch.object(m.os,'read',side_effect=chunks), self.assertRaises(m.StagingTLSContextError): m._read(999,2)
    def test_missing_portability_flag_and_proc_path(self):
        prep=self.preparation()
        with self.harness(),patch.object(m.os,'O_NOFOLLOW',0): self.rejected(prep)
        prep=self.preparation()
        with self.harness(),patch.object(m.os.path,'isdir',return_value=False): self.rejected(prep)
        self.assertEqual(self.opened,[])
    def test_file_and_directory_owner_and_inheritability(self):
        with open(self.leaf/'certificate.pem','rb') as handle:
            original=os.fstat(handle.fileno())
            attrs={name:getattr(original,name) for name in ['st_dev','st_ino','st_mode','st_uid','st_gid','st_nlink','st_size','st_mtime_ns','st_ctime_ns']}
            for field in ['st_uid','st_gid','st_nlink']:
                changed=dict(attrs);changed[field]+=1
                with self.subTest(field=field),patch.object(m.os,'fstat',return_value=types.SimpleNamespace(**changed)),self.assertRaises(m.StagingTLSContextError): m._file(handle.fileno(),self.policy,m._CERT_MAX)
            with patch.object(m.os,'get_inheritable',return_value=True),self.assertRaises(m.StagingTLSContextError): m._file(handle.fileno(),self.policy,m._CERT_MAX)
        fd=self.real_open(self.leaf,os.O_RDONLY|os.O_DIRECTORY)
        try:
            with patch.object(m.os,'get_inheritable',return_value=True),self.assertRaises(m.StagingTLSContextError): m._directory(fd,self.policy,True)
        finally: self.real_close(fd)
    def test_read_failure_cleanup(self):
        prep=self.preparation()
        with self.harness(),patch.object(m.os,'read',side_effect=OSError(MARKER)): self.rejected(prep)
        self.cleaned()
    def test_open_failure_cleanup(self):
        prep=self.preparation()
        with self.harness():
            hooked=m.os.open
            def fail(path,*args,**kwargs):
                if path=='private-key.pem': raise OSError(MARKER)
                return hooked(path,*args,**kwargs)
            with patch.object(m.os,'open',fail): self.rejected(prep)
        self.cleaned()
    def test_directory_mutation_after_load(self):
        prep=self.preparation()
        def mutate(*args,**kwargs): self.leaf.chmod(0o755)
        with self.harness(fake=True),patch.object(FakeContext,'load_cert_chain',mutate): self.rejected(prep)
        self.cleaned()
    def test_post_load_environment_identity_clock_rechecked(self):
        for kind in ['ambient','configured','keylog','clock','identity']:
            prep=self.preparation();env={}
            def mutate(ctx,*args,**kwargs):
                if kind=='ambient': os.environ['SSLKEYLOGFILE']=''
                elif kind=='configured': env['SSLKEYLOGFILE']=''
                elif kind=='keylog': ctx.keylog_filename=MARKER
                elif kind=='clock': m.time.time=lambda:BEGIN+3600
                else: m.os.getppid=lambda:999
            with self.subTest(kind=kind),self.harness(fake=True),patch.object(FakeContext,'load_cert_chain',mutate): self.rejected(prep,env)
            self.cleaned();self.opened.clear();self.closed.clear()

    def protocol_server_context(self):
        prep = self.preparation()
        with self.harness():
            context = prep.load(configured_environment={})
        self.cleaned()
        self.opened.clear()
        self.closed.clear()
        self.assertIsNone(context.keylog_filename)
        return context

    def synthetic_unverified_protocol_client(self, version, alpn=('http/1.1',)):
        # ONLY this local synthetic client bypasses peer verification: the pinned
        # public fixture is expired. No loader/server policy is altered.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.minimum_version = context.maximum_version = version
        if alpn is not None:
            context.set_alpn_protocols(list(alpn))
        self.assertIsNone(context.keylog_filename)
        return context

    def test_memorybio_synthetic_tls12_tls13_exact_sni_and_encrypted_roundtrip(self):
        for version, expected in [(ssl.TLSVersion.TLSv1_2, 'TLSv1.2'),
                                  (ssl.TLSVersion.TLSv1_3, 'TLSv1.3')]:
            with self.subTest(version=expected):
                server = self.protocol_server_context()
                client = self.synthetic_unverified_protocol_client(version)
                pair = BoundedMemoryTLS(server, client)
                pair.handshake()
                self.assertEqual(pair.errors, {})
                self.assertEqual(pair.complete, {'client', 'server'})
                for endpoint in [pair.client, pair.server]:
                    self.assertEqual(endpoint.version(), expected)
                    self.assertEqual(endpoint.selected_alpn_protocol(), 'http/1.1')
                    self.assertFalse(endpoint.session_reused)
                self.assertEqual(hashlib.sha256(pair.client.getpeercert(binary_form=True)).hexdigest(), self.policy.certificate_sha256)
                for sender, receiver, payload in [
                    (pair.client, pair.server, b'GET /synthetic-memorybio-only HTTP/1.1\r\nHost: localhost\r\n\r\n'),
                    (pair.server, pair.client, b'HTTP/1.1 200 OK\r\nContent-Length: 18\r\n\r\nsynthetic-response')]:
                    pair.wire.clear()
                    self.assertEqual(pair.exchange(sender, receiver, payload), payload)
                    self.assertTrue(pair.wire)
                    self.assertNotIn(payload, bytes(pair.wire))
                self.assertIsNone(server.keylog_filename)
                self.assertIsNone(client.keylog_filename)
                self.assertFalse(pair.client.session.has_ticket)

    def test_memorybio_synthetic_wrong_missing_and_nonexact_sni_rejected(self):
        for version in [ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3]:
            for hostname in [None, 'wrong.example', 'LOCALHOST', 'localhost.']:
                with self.subTest(version=version, hostname=hostname):
                    pair = BoundedMemoryTLS(self.protocol_server_context(),
                        self.synthetic_unverified_protocol_client(version), hostname)
                    pair.handshake()
                    self.assertEqual(pair.complete, set())
                    self.assertEqual(set(pair.errors), {'client', 'server'})
                    self.assertEqual(pair.errors['client'].reason, 'TLSV1_UNRECOGNIZED_NAME')

    def test_memorybio_synthetic_no_alpn_and_h2_only_negotiate_no_protocol(self):
        # Existing server policy advertises HTTP/1.1 but does not require ALPN.
        # Lack of overlap currently permits TLS with no selected application
        # protocol; this test records behavior, not an approval for HTTP/2.
        for version in [ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3]:
            for alpn in [None, ('h2',)]:
                with self.subTest(version=version, alpn=alpn):
                    pair = BoundedMemoryTLS(self.protocol_server_context(),
                        self.synthetic_unverified_protocol_client(version, alpn))
                    pair.handshake()
                    self.assertEqual(pair.errors, {})
                    self.assertEqual(pair.complete, {'client', 'server'})
                    self.assertIsNone(pair.client.selected_alpn_protocol())
                    self.assertIsNone(pair.server.selected_alpn_protocol())

    def test_memorybio_normal_verification_rejects_expired_public_fixture(self):
        for version in [ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3]:
            with self.subTest(version=version):
                client = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                client.minimum_version = client.maximum_version = version
                # Explicit local trust anchor isolates expiry from unknown CA.
                client.load_verify_locations(cafile=str(self.leaf/'certificate.pem'))
                self.assertEqual(client.verify_mode, ssl.CERT_REQUIRED)
                self.assertTrue(client.check_hostname)
                pair = BoundedMemoryTLS(self.protocol_server_context(), client)
                pair.handshake()
                error = pair.errors.get('client')
                self.assertIsInstance(error, ssl.SSLCertVerificationError)
                self.assertEqual(error.verify_code, 10)
                self.assertIn('expired', error.verify_message.lower())
                self.assertNotIn('client', pair.complete)

    def test_memorybio_synthetic_malformed_and_truncated_clienthello_rejected(self):
        pair = BoundedMemoryTLS(self.protocol_server_context(),
            self.synthetic_unverified_protocol_client(ssl.TLSVersion.TLSv1_2))
        pair.server_in.write(b'not a TLS record')
        with self.assertRaises(ssl.SSLError):
            pair.server.do_handshake()
        pair = BoundedMemoryTLS(self.protocol_server_context(),
            self.synthetic_unverified_protocol_client(ssl.TLSVersion.TLSv1_3))
        with self.assertRaises(ssl.SSLWantReadError):
            pair.client.do_handshake()
        hello = pair.client_out.read()
        self.assertGreater(len(hello), 10)
        pair.server_in.write(hello[:10])
        with self.assertRaises(ssl.SSLWantReadError):
            pair.server.do_handshake()
        pair.server_in.write_eof()
        with self.assertRaises(ssl.SSLEOFError):
            pair.server.do_handshake()

    def test_memorybio_contexts_are_fresh_but_loaded_context_has_no_deadline_enforcement(self):
        first = self.protocol_server_context()
        second = self.protocol_server_context()
        self.assertIsNot(first, second)
        # Loader window is checked at load, not at handshake. This is a lifetime
        # limitation, not authorization to keep serving after review expiry.
        with patch.object(m.time, 'time', return_value=self.policy.review_end + 1):
            pair = BoundedMemoryTLS(first,
                self.synthetic_unverified_protocol_client(ssl.TLSVersion.TLSv1_3))
            pair.handshake()
        self.assertEqual(pair.errors, {})
        self.assertEqual(pair.complete, {'client', 'server'})

    def test_memorybio_pump_budget_guards(self):
        pair = BoundedMemoryTLS(self.protocol_server_context(),
            self.synthetic_unverified_protocol_client(ssl.TLSVersion.TLSv1_3))
        pair.MAX_BYTES = 1
        with self.assertRaisesRegex(AssertionError, 'byte budget'):
            pair.handshake()
        pair = BoundedMemoryTLS(self.protocol_server_context(),
            self.synthetic_unverified_protocol_client(ssl.TLSVersion.TLSv1_3))
        pair.MAX_STEPS = 1
        with self.assertRaisesRegex(AssertionError, 'step budget'):
            pair.handshake()

if __name__=='__main__': unittest.main(verbosity=2)

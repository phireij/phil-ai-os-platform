"""Explicit descriptor-owned synthetic state custody, never an environment loader.

Policy values are operator assertions, not proof of mount/namespace isolation.
The provider must keep ancestors and the immutable key generation unchanged and
exclude all other writers/old binaries. A private 0700 directory, advisory lock,
and listed production exclusions cannot prove those host conditions. No paths,
IDs, keys or production locations are selected here. No I/O occurs at import or
policy validation. Only fixed state basenames are used after descriptor capture.
"""
from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path
import re
import secrets
import stat

_ERROR = 'staging_isolated_store_invalid'
_MAXIMUM = 64 * 1024 * 1024
LIVE = 'inquiries.enc'
LEDGER = 'deletions.enc'
LOCK = LIVE + '.writer.lock'

class IsolatedStoreConfigurationError(ValueError):
    pass

def _fail():
    raise IsolatedStoreConfigurationError(_ERROR) from None

def _path(value):
    if (type(value) is not str or not value.startswith('/') or value == '/'
            or '\\' in value or '\x00' in value or any(p in ('', '.', '..') for p in value.split('/')[1:])):
        _fail()
    return Path(value)

def _number(value):
    return type(value) is int and 0 <= value < 2**63

def _overlap(a, b):
    return a == b or a in b.parents or b in a.parents

def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

def _snapshot(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

def _finish(primary, cleanups):
    """Attempt each owned cleanup once; preserve the first control exception."""
    failure = primary
    for close in cleanups:
        try:
            close()
        except BaseException as exc:
            if failure is None or (isinstance(failure, Exception) and not isinstance(exc, Exception)):
                failure = exc
    if failure is not None:
        if isinstance(failure, Exception):
            _fail()
        raise failure

@dataclass(frozen=True)
class IsolatedStorePolicy:
    state_directory: str
    key_file: str
    reader_uid: int
    reader_gid: int
    # Exact sorted (absolute directory, uid, gid, mode) rows including root,
    # key parent, state leaf and every ancestor. No environment/default owner.
    directories: tuple[tuple[str, int, int, int], ...]
    state_identity: tuple[int, int]
    key_identity: tuple[int, int, int, int, int]
    excluded_roots: tuple[str, ...]
    namespace: str
    isolation_acknowledged: bool
    initialize_empty: bool

    def validate(self):
        state, key = _path(self.state_directory), _path(self.key_file)
        if _overlap(state, key.parent): _fail()
        if (type(self.reader_uid) is not int or not 0 < self.reader_uid < 2**32 - 1
                or type(self.reader_gid) is not int or not 0 <= self.reader_gid < 2**32 - 1
                or type(self.namespace) is not str or not re.fullmatch(r'synthetic-[A-Za-z0-9_-]{8,80}', self.namespace)
                or self.isolation_acknowledged is not True or type(self.initialize_empty) is not bool): _fail()
        expected = {str(state), str(key.parent), *(str(p) for p in state.parents), *(str(p) for p in key.parent.parents)}
        if type(self.directories) is not tuple: _fail()
        rows = {}
        for row in self.directories:
            if type(row) is not tuple or len(row) != 4: _fail()
            name, uid, gid, mode = row
            if (type(name) is not str or name not in expected or name in rows
                    or type(uid) is not int or not 0 <= uid < 2**32 - 1
                    or type(gid) is not int or not 0 <= gid < 2**32 - 1
                    or type(mode) is not int or mode not in (0o555, 0o755, 0o700)): _fail()
            rows[name] = (uid, gid, mode)
        if set(rows) != expected or tuple(sorted(self.directories)) != self.directories: _fail()
        if rows[str(state)] != (self.reader_uid, self.reader_gid, 0o700): _fail()
        if rows[str(key.parent)][2] != 0o555: _fail()
        for identity, length in ((self.state_identity, 2), (self.key_identity, 5)):
            if type(identity) is not tuple or len(identity) != length or not all(_number(v) for v in identity): _fail()
        if self.key_identity[2] not in (64, 65): _fail()
        if type(self.excluded_roots) is not tuple or not self.excluded_roots or len(set(self.excluded_roots)) != len(self.excluded_roots): _fail()
        for raw in self.excluded_roots:
            excluded = _path(raw)
            if _overlap(state, excluded) or _overlap(key, excluded): _fail()

class IsolatedStoreFiles:
    """Key bytes and pinned writable directory, owned by caller until claim()."""
    def __init__(self, policy):
        self.fd = None
        self.key = None
        self._claimed = False
        self._lease = None
        self.policy = policy
        fds = []
        primary = None
        try:
            if type(policy) is not IsolatedStorePolicy: _fail()
            policy.validate()
            if (os.name != 'posix' or (os.geteuid(), os.getegid()) != (policy.reader_uid, policy.reader_gid)
                    or any(not getattr(os, n, None) for n in ('O_NOFOLLOW','O_DIRECTORY','O_CLOEXEC','O_NONBLOCK','ST_RDONLY'))): _fail()
            rows = {row[0]: row[1:] for row in policy.directories}
            def directory(path):
                fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
                fds.append(fd)
                current = Path('/')
                self._directory(fd, rows[str(current)])
                for part in path.parts[1:]:
                    fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                    fds.append(fd)
                    current = current / part
                    self._directory(fd, rows[str(current)])
                return fd
            state = directory(Path(policy.state_directory))
            info = os.fstat(state)
            if (info.st_dev, info.st_ino) != policy.state_identity or os.fstatvfs(state).f_flag & os.ST_RDONLY: _fail()
            key_parent = directory(Path(policy.key_file).parent)
            if not os.fstatvfs(key_parent).f_flag & os.ST_RDONLY: _fail()
            key_fd = os.open(Path(policy.key_file).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=key_parent)
            fds.append(key_fd)
            before = self._regular(key_fd, 0o400, 65)
            if _identity(before) != policy.key_identity or not os.fstatvfs(key_fd).f_flag & os.ST_RDONLY: _fail()
            raw = self._read(key_fd, before.st_size, 65)
            if _snapshot(before) != _snapshot(self._regular(key_fd, 0o400, 65)): _fail()
            named = os.stat(Path(policy.key_file).name, dir_fd=key_parent, follow_symlinks=False)
            if _snapshot(named) != _snapshot(before): _fail()
            if not re.fullmatch(b'[0-9a-fA-F]{64}\\n?', raw): _fail()
            import hashlib, hmac
            master = bytes.fromhex(raw.decode('ascii').strip())
            self.key = hmac.new(master, b'ruby-staging-owner-isolated-v1\x00' +
                policy.namespace.encode('ascii'), hashlib.sha256).digest()
            # Distinct encryption/owner domain rejects ordinary Core snapshots
            # before startup maintenance. No legacy conversion or migration.
            self.fd = state
            fds.remove(state)
            self._check_directory()
        except BaseException as exc:
            primary = exc
        # A close failure is construction failure, including on the success path.
        try:
            _finish(primary, [lambda fd=fd: os.close(fd) for fd in reversed(fds)])
        except BaseException as exc:
            _finish(exc, [self.close])

    @staticmethod
    def _directory(fd, row):
        info = os.fstat(fd)
        if (not stat.S_ISDIR(info.st_mode) or (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != row or os.get_inheritable(fd)): _fail()

    def _regular(self, fd, mode=0o600, maximum=_MAXIMUM):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or (info.st_uid, info.st_gid) != (self.policy.reader_uid, self.policy.reader_gid)
                or stat.S_IMODE(info.st_mode) != mode or info.st_nlink != 1
                or not 0 <= info.st_size <= maximum or os.get_inheritable(fd)): _fail()
        return info

    def _check_directory(self):
        if self.fd is None or (os.geteuid(), os.getegid()) != (self.policy.reader_uid, self.policy.reader_gid): _fail()
        self._directory(self.fd, (self.policy.reader_uid, self.policy.reader_gid, 0o700))
        info = os.fstat(self.fd)
        if (info.st_dev, info.st_ino) != self.policy.state_identity or os.fstatvfs(self.fd).f_flag & os.ST_RDONLY: _fail()

    def _check(self):
        self._check_directory()
        if self._lease is None: _fail()
        self._lease.check()

    @staticmethod
    def _read(fd, size, maximum):
        parts = []
        total = 0
        while True:
            part = os.read(fd, min(1024 * 1024, maximum + 1 - total))
            if not part: break
            total += len(part)
            if total > maximum: _fail()
            parts.append(part)
        if total != size: _fail()
        return b''.join(parts)

    def acquire_lease(self):
        self._check_directory()
        if self._lease is not None: _fail()
        lease = _IsolatedLease(self)
        self._lease = lease
        return lease

    def claim(self):
        self._check()
        if self._claimed: _fail()
        self._claimed = True

    def read(self, name, *, missing=False, sync=False):
        self._check()
        if name not in (LIVE, LEDGER): _fail()
        fd = None
        primary = None
        result = None
        try:
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.fd)
            except FileNotFoundError:
                if not missing: raise
            if fd is not None:
                before = self._regular(fd)
                if sync: os.fsync(fd)
                result = self._read(fd, before.st_size, _MAXIMUM)
                if _snapshot(before) != _snapshot(self._regular(fd)): _fail()
                if _snapshot(before) != _snapshot(os.stat(name, dir_fd=self.fd, follow_symlinks=False)): _fail()
                if sync: os.fsync(self.fd)
            self._check()
        except BaseException as exc:
            primary = exc
        _finish(primary, [] if fd is None else [lambda: os.close(fd)])
        return result

    def initial_pair(self):
        pair = (self.read(LIVE, missing=True), self.read(LEDGER, missing=True))
        if self.policy.initialize_empty:
            if pair != (None, None): _fail()
        elif any(value is None for value in pair): _fail()
        return pair

    def write(self, name, encoded, *, overwrite=True):
        self._check()
        if name not in (LIVE, LEDGER) or type(encoded) is not bytes or not 1 <= len(encoded) <= _MAXIMUM: _fail()
        # Validate any current target without following it. A target replacement
        # by a malicious same-UID/host writer is outside the asserted isolation;
        # replacement never follows that target even if such a writer races us.
        current = self.read(name, missing=True)
        if not overwrite and current is not None: _fail()
        temporary = '.' + name + '.' + secrets.token_hex(16) + '.tmp'
        fd = None
        created = False
        primary = None
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.fd)
            created = True
            self._regular(fd)
            data = memoryview(encoded)
            while data:
                count = os.write(fd, data)
                if count <= 0: _fail()
                data = data[count:]
            os.fsync(fd)
            self._regular(fd)
            retired, fd = fd, None
            os.close(retired)
            self._check()
            if overwrite:
                os.replace(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
                created = False
            else:
                os.link(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd, follow_symlinks=False)
                os.unlink(temporary, dir_fd=self.fd)
                created = False
            os.fsync(self.fd)
            self._check()
        except BaseException as exc:
            primary = exc
        cleanups = [] if fd is None else [lambda: os.close(fd)]
        if created: cleanups.append(lambda: os.unlink(temporary, dir_fd=self.fd))
        _finish(primary, cleanups)

    def close(self):
        fd, self.fd = self.fd, None
        lease, self._lease = self._lease, None
        self.key = None
        _finish(None, ([] if lease is None or lease.fd is None else [lease.close]) +
                ([] if fd is None else [lambda: os.close(fd)]))

class _IsolatedLease:
    def __init__(self, files):
        self.files = files
        self.fd = None
        try:
            import fcntl
            self.fd = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600, dir_fd=files.fd)
            info = files._regular(self.fd, maximum=0)
            self.identity = (info.st_dev, info.st_ino)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.check()
        except BaseException as exc:
            _finish(exc, [self.close])

    def check(self):
        if self.fd is None: _fail()
        info = self.files._regular(self.fd, maximum=0)
        named = os.stat(LOCK, dir_fd=self.files.fd, follow_symlinks=False)
        if (info.st_dev, info.st_ino) != self.identity or _snapshot(info) != _snapshot(named): _fail()

    def close(self):
        fd, self.fd = self.fd, None
        if fd is not None: os.close(fd)

@dataclass(frozen=True)
class StagingOwnerStartupPolicy:
    """Nonsecret explicit master policy; exact private composition is child-only."""
    generation: str
    files: IsolatedStorePolicy
    issuer: str
    owner_subject: str
    project_id: str
    source_system: str
    source_instance: str
    policy_version: str
    catalog_json: str
    catalog_revision: str
    source_retention_enabled: bool
    synthetic_only: bool
    source_intake_enabled: bool = False

    def validate(self):
        from hashlib import sha256
        import json
        from ruby_staging_id_token import ISSUER
        if (type(self.source_intake_enabled) is not bool
                or type(self.files) is not IsolatedStorePolicy or self.issuer != ISSUER
                or type(self.generation) is not str or not re.fullmatch('[0-9a-f]{32}', self.generation)
                or type(self.owner_subject) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,255}', self.owner_subject)
                or self.synthetic_only is not True or self.source_retention_enabled is not True
                or type(self.catalog_json) is not str or not 1 <= len(self.catalog_json.encode('utf-8')) <= 2*1024*1024
                or type(self.catalog_revision) is not str or not re.fullmatch('[0-9a-f]{64}', self.catalog_revision)):
            _fail()
        for value in (self.project_id, self.source_system, self.source_instance, self.policy_version):
            if type(value) is not str or not re.fullmatch('[A-Za-z0-9_.:-]{1,120}', value): _fail()
        self.files.validate()
        # Canonical JSON rules eliminate duplicate/nonfinite/alternate encodings;
        # the private mapper performs the complete exact catalog validation.
        value = json.loads(self.catalog_json)
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if type(value) is not dict or encoded != self.catalog_json or sha256(encoded.encode()).hexdigest() != self.catalog_revision: _fail()

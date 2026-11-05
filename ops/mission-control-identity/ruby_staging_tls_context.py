"""Inactive standalone certificate/context preparation; never a serving entrypoint.

The trusted operator binds generation to the certificate fingerprint in explicit
policy and must publish immutable files with no concurrent host-side writer.
Descriptor paths avoid original-name substitution, not inode mutation. PID checks
are additional refusal checks, not proof of the approved worker lifecycle. No
launcher, callback selection, listener, renewal or readiness is implemented here.
A returned SSLContext is mutable. It is not approved for serving by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
import re
import ssl
import stat
import time

_ERROR = "staging_tls_context_invalid"
_CERT_MAX = 65536
_KEY_MAX = 16384

class StagingTLSContextError(ValueError):
    pass

def _fail():
    raise StagingTLSContextError(_ERROR) from None

@dataclass(frozen=True)
class StagingTLSPolicy:
    generation: str
    hostname: str
    certificate_sha256: str
    reader_uid: int
    reader_gid: int
    directory_uid: int
    directory_gid: int
    review_start: int
    review_end: int
    renewal_margin_seconds: int

    def validate(self):
        if (type(self.generation) is not str or re.fullmatch(r"[0-9a-f]{32}", self.generation) is None
                or type(self.certificate_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", self.certificate_sha256) is None):
            _fail()
        if (type(self.hostname) is not str or not self.hostname.isascii()
                or not 1 <= len(self.hostname) <= 253 or self.hostname != self.hostname.lower()
                or self.hostname.endswith(".") or re.fullmatch(r"[0-9.]+", self.hostname)):
            _fail()
        if any(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None
               for label in self.hostname.split(".")):
            _fail()
        for value in (self.reader_uid, self.reader_gid, self.directory_uid, self.directory_gid):
            if type(value) is not int or not 0 <= value < 2**32 - 1:
                _fail()
        if self.reader_uid == 0:
            _fail()
        if any(type(v) is not int or not 0 <= v < 2**53 for v in
               (self.review_start, self.review_end, self.renewal_margin_seconds)):
            _fail()
        if not self.review_start < self.review_end or self.renewal_margin_seconds == 0:
            _fail()

def _snapshot(st):
    return tuple(getattr(st, n) for n in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid",
        "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"))

def _directory(fd, p, leaf):
    st = os.fstat(fd)
    if (not stat.S_ISDIR(st.st_mode) or (st.st_uid, st.st_gid) != (p.directory_uid, p.directory_gid)
            or stat.S_IMODE(st.st_mode) not in ({0o555} if leaf else {0o555, 0o755})
            or os.get_inheritable(fd) or (leaf and not os.fstatvfs(fd).f_flag & os.ST_RDONLY)):
        _fail()
    return _snapshot(st)

def _file(fd, p, maximum):
    st = os.fstat(fd)
    if (not stat.S_ISREG(st.st_mode) or (st.st_uid, st.st_gid) != (p.reader_uid, p.reader_gid)
            or stat.S_IMODE(st.st_mode) != 0o400 or st.st_nlink != 1
            or not 1 <= st.st_size <= maximum or os.get_inheritable(fd)
            or not os.fstatvfs(fd).f_flag & os.ST_RDONLY):
        _fail()
    return _snapshot(st)

def _read(fd, size):
    out = bytearray()
    while len(out) <= size:
        part = os.read(fd, min(4096, size + 1 - len(out)))
        if not part:
            if len(out) != size:
                _fail()
            return bytes(out)
        out.extend(part)
    _fail()

def _cert(raw, p):
    # Bounded input only. Certificate details never enter diagnostics.
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    certificates = x509.load_pem_x509_certificates(raw)
    if not 1 <= len(certificates) <= 8:
        _fail()
    leaf = certificates[0]
    if leaf.fingerprint(hashes.SHA256()).hex() != p.certificate_sha256:
        _fail()
    names = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    if p.hostname not in names.get_values_for_type(x509.DNSName):
        _fail()
    # No CN/wildcard matching or browser-trust claim. Key pairing is checked by
    # OpenSSL during load_cert_chain. Chain/usage/algorithm acceptance is separate.
    if (leaf.not_valid_before_utc.timestamp() > p.review_start
            or leaf.not_valid_after_utc.timestamp() <= p.review_end + p.renewal_margin_seconds):
        _fail()

def _password_refused():
    # OpenSSL must never fall back to terminal prompting for an encrypted key.
    _fail()

def _finish(fds, primary):
    for fd in reversed(fds):
        try:
            os.close(fd)
        except BaseException as failure:
            if primary is None or (isinstance(primary, Exception) and not isinstance(failure, Exception)):
                primary = failure
    if primary is not None:
        if isinstance(primary, Exception):
            _fail()
        raise primary

class StagingTLSContextPreparation:
    """Single-use standalone preparation with no production import or activation.

    Construct in the intended parent, load only after fork/effective identity.
    The caller must still be integrated into the reviewed exact worker lifecycle.
    The private-key file is loaded by OpenSSL, not copied into Python or stored
    on this object. Python reference cleanup does not guarantee secret erasure.
    """
    def __init__(self, *, enabled=False, policy=None):
        if type(enabled) is not bool:
            _fail()
        if enabled:
            if type(policy) is not StagingTLSPolicy:
                _fail()
            policy.validate()
        self._enabled = enabled
        self._policy = policy if enabled else None
        self._creator_pid = os.getpid()
        self._attempted = False

    def load(self, *, configured_environment):
        if not self._enabled:
            return None
        if self._attempted:
            _fail()
        self._attempted = True
        p = self._policy
        fds, directories, primary, context = [], [], None, None
        try:
            p.validate()
            if (type(configured_environment) is not dict
                    or any(type(k) is not str or type(v) is not str for k, v in configured_environment.items())
                    or "SSLKEYLOGFILE" in configured_environment or "SSLKEYLOGFILE" in os.environ
                    or os.getpid() == self._creator_pid or os.getppid() != self._creator_pid
                    or (os.geteuid(), os.getegid()) != (p.reader_uid, p.reader_gid)
                    or os.name != "posix" or not os.path.isdir("/proc/self/fd")):
                _fail()
            now = time.time()
            if not math.isfinite(now) or not p.review_start <= now < p.review_end:
                _fail()
            for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK", "ST_RDONLY"):
                if type(getattr(os, name, None)) is not int or not getattr(os, name):
                    _fail()
            dflags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            fflags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
            parent = os.open("/", dflags)
            fds.append(parent)
            directories.append((parent, False, _directory(parent, p, False)))
            for component in ("run", "secrets", "ruby-staging-tls"):
                parent = os.open(component, dflags, dir_fd=parent)
                fds.append(parent)
                leaf = component == "ruby-staging-tls"
                directories.append((parent, leaf, _directory(parent, p, leaf)))
            opened = []
            for name, maximum in (("certificate.pem", _CERT_MAX), ("private-key.pem", _KEY_MAX)):
                fd = os.open(name, fflags, dir_fd=parent)
                fds.append(fd)
                opened.append((fd, maximum, _file(fd, p, maximum)))
            cert_fd, _, cert_before = opened[0]
            _cert(_read(cert_fd, cert_before[6]), p)
            # Keep both descriptors live. /proc reopens these pinned objects, not
            # the originally supplied path. Immutable host publication is required.
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.maximum_version = ssl.TLSVersion.TLSv1_3
            context.set_alpn_protocols(["http/1.1"])
            context.options |= ssl.OP_NO_TICKET
            context.num_tickets = 0
            def sni(connection, name, initial):
                if name != p.hostname or initial is not context:
                    return ssl.ALERT_DESCRIPTION_UNRECOGNIZED_NAME
                return None
            context.sni_callback = sni
            if context.keylog_filename is not None:
                _fail()
            context.load_cert_chain(f"/proc/self/fd/{cert_fd}",
                f"/proc/self/fd/{opened[1][0]}", password=_password_refused)
            for fd, maximum, before in opened:
                if _file(fd, p, maximum) != before:
                    _fail()
            for fd, leaf, before in directories:
                if _directory(fd, p, leaf) != before:
                    _fail()
            if (context.keylog_filename is not None or "SSLKEYLOGFILE" in os.environ
                    or "SSLKEYLOGFILE" in configured_environment
                    or (os.geteuid(), os.getegid()) != (p.reader_uid, p.reader_gid)
                    or os.getpid() == self._creator_pid or os.getppid() != self._creator_pid
                    or not p.review_start <= time.time() < p.review_end):
                _fail()
        except BaseException as failure:
            primary = failure
        _finish(fds, primary)
        return context

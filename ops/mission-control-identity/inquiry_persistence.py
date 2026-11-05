"""Fail-closed persistence guards for the source-only inquiry milestone.

No background work, environment configuration, transport, or provider calls.
The stable advisory-lock inode is never unlinked while stores may exist.
"""
from __future__ import annotations

import os
import stat
import threading
import weakref
from pathlib import Path


def _error(code):
    from conversation_store import ConversationConfigurationError
    return ConversationConfigurationError(code)


def _cleanup_resources(actions, *, primary=None, error_code=None):
    """Attempt every retired resource once without replacing a primary control.

    Callers retain and re-raise their primary exception. Otherwise the first
    cleanup control wins over ordinary failures, which expose only a fixed
    code (or are best-effort when no code is supplied).
    """
    control = None
    failed = False
    for action in actions:
        try:
            action()
        except BaseException as exc:
            failed = True
            if not isinstance(exc, Exception) and control is None:
                control = exc
    if primary is not None and not isinstance(primary, Exception):
        return
    if control is not None:
        raise control from None
    if primary is None and failed and error_code is not None:
        raise _error(error_code) from None


class StoreLease:
    """Legacy-only readers/writers share; inquiry custody has one exclusive owner.

    Shared mode preserves existing legacy semantics, not multiwriter safety.
    Every upgraded writer participates. Validation-only preflight never writes
    or acquires this lease and cannot become a writer after construction.
    Old binaries must not share a volume with this candidate.
    """
    def __init__(self, state_path: Path, *, exclusive: bool):
        self.fd = None
        if os.name != "posix":
            raise _error("conversation_writer_lock_unsupported")
        import fcntl
        path = state_path.with_name(state_path.name + ".writer.lock")
        try:
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            self.fd = fd
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_nlink != 1:
                raise _error("conversation_writer_lock_invalid")
            mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(fd, mode | fcntl.LOCK_NB)
            # A changed/unlinked lock inode must not create a second ownership domain.
            named = path.lstat()
            if named.st_ino != info.st_ino or named.st_dev != info.st_dev:
                raise _error("conversation_writer_lock_invalid")
        except BaseException as primary:
            _cleanup_resources((self.close,), primary=primary)
            if not isinstance(primary, Exception):
                raise
            raise _error("conversation_writer_unavailable") from None

    def close(self):
        if self.fd is not None:
            fd = self.fd
            # close(2) may already have retired the descriptor when it fails.
            # Never retry an uncertain close against a possibly reused number.
            self.fd = None
            _cleanup_resources((lambda: os.close(fd),), error_code="conversation_writer_unavailable")

    def __del__(self):
        try:
            self.close()
        except BaseException:
            pass


class FencedStoreLock:
    def __init__(self, store):
        self.store = weakref.ref(store)
        self.raw = threading.Lock()

    def __enter__(self):
        self.raw.acquire()
        store = self.store()
        if store is None or store._closed or store._persistence_fenced:
            self.raw.release()
            from conversation_store import ConversationRequestError
            raise ConversationRequestError("conversation_store_fenced", 503)
        return self

    def __exit__(self, *args):
        self.raw.release()


def read_preflight_snapshots(*paths: Path) -> tuple[bytes, ...]:
    """Capture protected atomic snapshots without creating or locking any file.

    Hold both inodes open before reading. Reject a replacement or modification
    during capture instead of guessing which generation is authoritative. A
    stable pair may contain a committed deletion ledger ahead of the live
    snapshot; the caller must replay that ledger in memory before any reads.
    This is an observational snapshot, never a writer lease or recovery proof.
    """
    descriptors = []
    try:
        for path in paths:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            descriptors.append(fd)
        before = [os.fstat(fd) for fd in descriptors]
        maximum = 64 * 1024 * 1024
        def identity(info):
            return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
                    info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        for info in before:
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > maximum:
                raise _error("conversation_preflight_snapshot_invalid")
        captured = []
        for fd in descriptors:
            chunks = []
            size = 0
            while True:
                chunk = os.read(fd, min(1024 * 1024, maximum + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > maximum:
                    raise _error("conversation_preflight_snapshot_invalid")
            captured.append(b"".join(chunks))
        for path, fd, info in zip(paths, descriptors, before):
            if identity(os.fstat(fd)) != identity(info) or identity(path.lstat()) != identity(info):
                raise _error("conversation_preflight_snapshot_changed")
        return tuple(captured)
    except OSError:
        raise _error("conversation_preflight_snapshot_unavailable") from None
    finally:
        for fd in descriptors:
            os.close(fd)


def synchronize_snapshot(path: Path):
    """Verify protected file and synchronize observed bytes before unfencing."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise _error("conversation_snapshot_permissions")
        os.fsync(fd)
        named = path.lstat()
        if named.st_ino != info.st_ino or named.st_dev != info.st_dev:
            raise _error("conversation_snapshot_changed")
    finally:
        os.close(fd)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)

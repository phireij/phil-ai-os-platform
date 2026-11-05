"""Local admission bookkeeping only. No runtime actuator or retirement authority.

Linux/POSIX, honest local fsync/rename/flock, protected single-owner storage.
See README.staging-durable-admission.md for mandatory storage and integration assumptions.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import errno
import fcntl
from functools import wraps
import hashlib
import json
import os
import re
import stat
import threading
import uuid

MAX_BYTES = 32768
MAX_REVISION = (1 << 63) - 1
LOCK = "owner.lock"
JOURNAL = "journal.json"
STATES = frozenset({"CLOSED", "CREATE_INTENT", "CREATED", "START_INTENT",
                    "STARTING", "RETIRING", "SEALED", "UNKNOWN"})
KINDS = frozenset({"START_RESPONSE_OK", "START_RESPONSE_ERROR", "START_RESPONSE_LOST",
                   "EXIT_REPORTED", "RUNNING_REPORTED", "OBSERVER_LOST", "CONFLICT"})
REQUIREMENTS = (
    "Trusted adapter must verify selected daemon and exact immutable object configuration.",
    "All authorized start/recreate paths must be controlled; token is not a Docker fence.",
    "Adapter must verify never-started object, restart-off and private PID namespace.",
    "Independent watchdog must already be armed; observer registration must be acknowledged.",
    "Post-start runtime retirement and request settlement remain unverified by this core.",
)


class AdmissionError(Exception):
    """Fail-closed result; never a returned operation permit."""


class Busy(AdmissionError):
    pass


class StorageUnsafe(AdmissionError):
    pass


class Denied(AdmissionError):
    pass


def _public(method):
    """Guard reentrancy and redact public storage failures.

    Internal implementations call private helpers, never another public operation.
    Fork-child close only drops its inherited descriptors; it cannot affect the
    parent's operation flag or explicitly unlock its shared open file description.
    """
    @wraps(method)
    def call(*args, **kwargs):
        owner = args[0] if args else None
        guard = isinstance(owner, Session) and owner._pid == os.getpid()
        if guard:
            # A rejected foreign thread must never touch the owner's guard: a
            # check/set/reset race could otherwise clear a live operation flag.
            if owner._thread is not threading.current_thread():
                raise Denied("session belongs to another thread")
            if owner._active_operation:
                raise Denied("session operation already active; reentrant calls denied")
            owner._active_operation = True
        try:
            return method(*args, **kwargs)
        except (OSError, StorageUnsafe) as exc:
            if isinstance(owner, Session):
                owner._poisoned = True
            if isinstance(exc, StorageUnsafe):
                raise StorageUnsafe(str(exc)) from None
            raise StorageUnsafe("local storage unavailable or unsafe") from None
        finally:
            if guard:
                owner._active_operation = False
    return call


def _exact_keys(value, keys):
    return type(value) is dict and set(value) == set(keys)


def _text(value, max_len=128):
    return type(value) is str and 1 <= len(value) <= max_len and all(
        32 <= ord(c) <= 126 for c in value)


def _hex(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _id(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value) is not None


def _integer(value, low=0):
    return type(value) is int and low <= value <= MAX_REVISION


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _no_duplicates(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("duplicate JSON key")
        d[k] = v
    return d


def _identity(st):
    return [st.st_dev, st.st_ino]


def _check_directory(st):
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or st.st_mode & 0o022:
        raise StorageUnsafe("state directory must be owned by this uid and not group/other writable")


def _check_file(st):
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_nlink != 1
            or st.st_mode & 0o022):
        raise StorageUnsafe("state files must be regular, single-link, owned and not group/other writable")


def _open_directory(path):
    if type(path) is not str or not path.startswith("/") or path == "/":
        raise StorageUnsafe("explicit absolute state directory required")
    parts = path.split("/")[1:]
    if any(p in ("", ".", "..") for p in parts):
        raise StorageUnsafe("noncanonical state directory")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in parts:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                          dir_fd=fd)
            previous_fd, fd = fd, nxt
            os.close(previous_fd)
        _check_directory(os.fstat(fd))
        return fd
    except BaseException:
        os.close(fd)
        raise


def _validate(rec):
    if not _exact_keys(rec, {"schema", "journal_id", "directory_identity", "lock_identity", "revision",
                             "daemon", "bootstrap_ref", "state", "generation", "unknown_reason"}):
        raise StorageUnsafe("invalid record shape")
    if type(rec["schema"]) is not int or rec["schema"] != 1 or not _id(rec["journal_id"]):
        raise StorageUnsafe("unsupported journal")
    for key in ("directory_identity", "lock_identity"):
        if type(rec[key]) is not list or len(rec[key]) != 2 or not all(_integer(x) for x in rec[key]):
            raise StorageUnsafe("invalid inode identity")
    if (not _integer(rec["revision"]) or not _text(rec["bootstrap_ref"])
            or not _exact_keys(rec["daemon"], {"endpoint_ref", "identity"})
            or not _text(rec["daemon"]["endpoint_ref"]) or not _text(rec["daemon"]["identity"])
            or type(rec["state"]) is not str or rec["state"] not in STATES
            or not _text(rec["unknown_reason"])):
        raise StorageUnsafe("invalid metadata")
    g = rec["generation"]
    if g is None:
        if rec["state"] not in {"CLOSED", "UNKNOWN"}:
            raise StorageUnsafe("missing generation")
        return
    if rec["state"] == "CLOSED" or not _exact_keys(g, {"id", "spec_digest", "policy_digest", "watchdog_ref",
            "full_id", "observer_ref", "start_consumed", "attempt_id", "start_revision", "sealed",
            "terminal_observed", "last_observation", "observation_sequence"}):
        raise StorageUnsafe("invalid generation")
    if not _id(g["id"]) or not _hex(g["spec_digest"]) or not _hex(g["policy_digest"]) or not _text(g["watchdog_ref"]):
        raise StorageUnsafe("invalid immutable generation binding")
    if g["full_id"] is not None and not _hex(g["full_id"]):
        raise StorageUnsafe("full object id required")
    if g["observer_ref"] is not None and not _id(g["observer_ref"]):
        raise StorageUnsafe("invalid observer")
    if any(type(g[k]) is not bool for k in ("start_consumed", "sealed", "terminal_observed")):
        raise StorageUnsafe("invalid monotonic flags")
    if not _integer(g["observation_sequence"]):
        raise StorageUnsafe("invalid sequence")
    if g["last_observation"] is not None and not _hex(g["last_observation"]):
        raise StorageUnsafe("invalid observation hash")
    if (g["observation_sequence"] == 0) != (g["last_observation"] is None):
        raise StorageUnsafe("inconsistent observation")
    if g["observer_ref"] is not None and g["full_id"] is None:
        raise StorageUnsafe("observer lacks object binding")
    if not g["start_consumed"] and (g["terminal_observed"] or g["observation_sequence"] != 0):
        raise StorageUnsafe("execution observation lacks consumed attempt")
    if rec["revision"] == 0:
        raise StorageUnsafe("generation lacks durable revision")
    if g["start_consumed"]:
        if (not _id(g["attempt_id"]) or not _integer(g["start_revision"], 1)
                or g["start_revision"] > rec["revision"] or g["full_id"] is None or g["observer_ref"] is None):
            raise StorageUnsafe("invalid consumed attempt")
    elif g["attempt_id"] is not None or g["start_revision"] is not None:
        raise StorageUnsafe("attempt present without consumption")
    if rec["state"] == "CREATE_INTENT" and (g["full_id"] is not None or g["start_consumed"]):
        raise StorageUnsafe("invalid create state")
    if rec["state"] == "CREATED" and (g["full_id"] is None or g["start_consumed"]):
        raise StorageUnsafe("invalid created state")
    if rec["state"] in {"START_INTENT", "STARTING", "RETIRING"} and not g["start_consumed"]:
        raise StorageUnsafe("state lacks consumed attempt")
    if rec["state"] == "SEALED" and not g["sealed"]:
        raise StorageUnsafe("missing terminal seal")
    if g["sealed"] and rec["state"] not in {"SEALED", "UNKNOWN"}:
        raise StorageUnsafe("terminal seal regression")
    if g["terminal_observed"] and rec["state"] not in {"RETIRING", "SEALED", "UNKNOWN"}:
        raise StorageUnsafe("terminal observation regression")


@dataclass(frozen=True)
class StartPermit:
    journal_id: str
    revision: int
    generation: str
    spec_digest: str
    policy_digest: str
    daemon_endpoint_ref: str
    daemon_identity: str
    full_id: str
    attempt_id: str
    observer_ref: str
    watchdog_ref: str
    requirements: tuple[str, ...] = REQUIREMENTS


class Session:
    """One process/thread owns this locked session; never share it across fork.

    No lease, timeout, automatic initialization, runtime import or runtime I/O.
    A descriptor is not a daemon-enforced capability and cannot prevent its holder
    from copying it. An eventual trusted single-use adapter must preserve the rule.
    """

    def __init__(self):
        raise TypeError("use initialize() or open()")

    @classmethod
    def _new(cls, path, directory_fd, lock_fd):
        self = object.__new__(cls)
        self._path, self._directory_fd, self._lock_fd = path, directory_fd, lock_fd
        self._pid, self._thread = os.getpid(), threading.current_thread()
        self._poisoned = False
        self._active_operation = False
        self._closed = False
        self._record = None
        self._directory_identity = _identity(os.fstat(directory_fd))
        self._lock_identity = _identity(os.fstat(lock_fd))
        return self

    @staticmethod
    def _checkpoint(phase):
        """Internal test seam, patched only by local fault tests; no configured callback."""

    @classmethod
    @_public
    def initialize(cls, path, *, endpoint_ref, daemon_identity, reconciliation_ref):
        """Explicit bootstrap in a protected EMPTY directory already created by operator.

        reconciliation_ref is an audit reference, not proof. The caller must already
        have reconciled absence of owned work externally. Any partial initialization
        leaves files that block another initialize; this API has no reset/repair.
        """
        if not all(_text(v) for v in (endpoint_ref, daemon_identity, reconciliation_ref)):
            raise Denied("bounded nonsecret bootstrap references required")
        dfd = _open_directory(path)
        lfd = None
        self = None
        try:
            if os.listdir(dfd):
                raise StorageUnsafe("initialization requires an explicitly fresh empty directory")
            lfd = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                          0o600, dir_fd=dfd)
            fcntl.flock(lfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self = cls._new(path, dfd, lfd)
            journal_id = uuid.uuid4().hex
            lock_bytes = memoryview(journal_id.encode("ascii"))
            while lock_bytes:
                n = os.write(lfd, lock_bytes)
                if n <= 0:
                    raise OSError(errno.EIO, "short lock write")
                lock_bytes = lock_bytes[n:]
            cls._checkpoint("init_before_lock_fsync")
            os.fsync(lfd)
            cls._checkpoint("init_after_lock_fsync")
            os.fsync(dfd)
            cls._checkpoint("init_after_directory_fsync")
            rec = {"schema": 1, "journal_id": journal_id, "directory_identity": self._directory_identity,
                   "lock_identity": self._lock_identity, "revision": 0,
                   "daemon": {"endpoint_ref": endpoint_ref, "identity": daemon_identity},
                   "bootstrap_ref": reconciliation_ref, "state": "CLOSED", "generation": None,
                   "unknown_reason": "none"}
            self._write(rec, initial=True)
            return self
        except BaseException:
            if self is not None:
                self.close()
            else:
                if lfd is not None:
                    os.close(lfd)
                os.close(dfd)
            raise

    @classmethod
    @_public
    def open(cls, path, *, endpoint_ref, daemon_identity):
        if not all(_text(v) for v in (endpoint_ref, daemon_identity)):
            raise Denied("bounded daemon binding required")
        dfd = _open_directory(path)
        lfd = None
        self = None
        try:
            lfd = os.open(LOCK, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dfd)
            _check_file(os.fstat(lfd))
            try:
                fcntl.flock(lfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Busy("another owner retains the stable lock") from None
            self = cls._new(path, dfd, lfd)
            self._record = self._read()
            self._verify_storage()
            if self._record["daemon"] != {"endpoint_ref": endpoint_ref, "identity": daemon_identity}:
                self._unknown("daemon binding mismatch")
                raise Denied("daemon binding mismatch; original binding retained in UNKNOWN")
            if self._record["state"] not in {"CLOSED", "UNKNOWN", "SEALED"}:
                self._unknown("recovered unfinished generation or observation continuity")
            return self
        except BaseException:
            if self is not None:
                self.close()
            else:
                if lfd is not None:
                    os.close(lfd)
                os.close(dfd)
            raise

    def _owner(self):
        if self._closed or self._pid != os.getpid() or self._thread is not threading.current_thread():
            raise Denied("session belongs to another process/thread or is closed")
        if self._poisoned:
            raise StorageUnsafe("session poisoned by uncertain storage; reopen for reconciliation")

    def _verify_storage(self):
        self._owner()
        dfd = _open_directory(self._path)
        try:
            if _identity(os.fstat(dfd)) != self._directory_identity:
                raise StorageUnsafe("state directory replaced")
        finally:
            os.close(dfd)
        dst = os.fstat(self._directory_fd)
        _check_directory(dst)
        lst = os.stat(LOCK, dir_fd=self._directory_fd, follow_symlinks=False)
        fst = os.fstat(self._lock_fd)
        _check_file(lst)
        _check_file(fst)
        if _identity(lst) != self._lock_identity or _identity(fst) != self._lock_identity:
            raise StorageUnsafe("stable lock inode replaced")
        if self._record is not None:
            if (self._record["directory_identity"] != self._directory_identity
                    or self._record["lock_identity"] != self._lock_identity):
                raise StorageUnsafe("stored directory/lock identity mismatch")
            if os.pread(self._lock_fd, 65, 0) != self._record["journal_id"].encode("ascii"):
                raise StorageUnsafe("stable lock contents changed")

    def _read(self):
        fd = os.open(JOURNAL, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=self._directory_fd)
        try:
            st = os.fstat(fd)
            _check_file(st)
            if st.st_size > MAX_BYTES:
                raise StorageUnsafe("journal too large")
            chunks = []
            length = 0
            while True:
                chunk = os.read(fd, MAX_BYTES + 1 - length)
                if not chunk:
                    break
                chunks.append(chunk)
                length += len(chunk)
                if length > MAX_BYTES:
                    raise StorageUnsafe("journal too large")
            data = b"".join(chunks)
            if len(data) != st.st_size:
                raise StorageUnsafe("journal changed during read")
        finally:
            os.close(fd)
        try:
            env = json.loads(data.decode("ascii"), object_pairs_hook=_no_duplicates,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid constant")))
            if not _exact_keys(env, {"record", "sha256"}) or not _hex(env["sha256"]):
                raise ValueError("invalid envelope")
            rec = env["record"]
            if hashlib.sha256(_canonical(rec)).hexdigest() != env["sha256"]:
                raise ValueError("checksum mismatch")
            _validate(rec)
            return rec
        except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
            raise StorageUnsafe("malformed or corrupt journal; no automatic repair") from exc

    def _write(self, rec, *, initial=False):
        """No success before replace, directory fsync, and durable read-back agree."""
        self._verify_storage()
        _validate(rec)
        tmp = "pending-" + uuid.uuid4().hex
        fd = None
        try:
            if not initial and self._read() != self._record:
                raise StorageUnsafe("journal externally changed or rolled back")
            if initial and JOURNAL in os.listdir(self._directory_fd):
                raise StorageUnsafe("journal unexpectedly appeared")
            payload = _canonical({"record": rec, "sha256": hashlib.sha256(_canonical(rec)).hexdigest()})
            if len(payload) > MAX_BYTES:
                raise StorageUnsafe("bounded journal exceeded")
            self._checkpoint("before_temp_open")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=self._directory_fd)
            self._checkpoint("before_write")
            view = memoryview(payload)
            while view:
                n = os.write(fd, view)
                if n <= 0:
                    raise OSError(errno.EIO, "short journal write")
                view = view[n:]
            self._checkpoint("after_write")
            self._checkpoint("before_file_fsync")
            os.fsync(fd)
            self._checkpoint("after_file_fsync")
            closing_fd, fd = fd, None
            os.close(closing_fd)
            self._verify_storage()
            self._checkpoint("before_replace")
            os.replace(tmp, JOURNAL, src_dir_fd=self._directory_fd, dst_dir_fd=self._directory_fd)
            self._checkpoint("after_replace")
            self._checkpoint("before_directory_fsync")
            os.fsync(self._directory_fd)
            self._checkpoint("after_directory_fsync")
            self._verify_storage()
            if self._read() != rec:
                raise StorageUnsafe("durable write read-back mismatch")
            self._record = rec
            self._checkpoint("after_durable_commit")
        except BaseException:
            self._poisoned = True
            # Do not overwrite ambiguous/corrupt storage or pretend a second fsync works.
            # A successor validates and persists UNKNOWN before returning a session.
            raise
        finally:
            if fd is not None:
                os.close(fd)
            # Leave interrupted temporary files as evidence. They are never adopted.

    def _begin(self, revision):
        self._verify_storage()
        current = self._read()
        if current != self._record:
            self._poisoned = True
            raise StorageUnsafe("journal externally changed or rolled back")
        if not _integer(revision) or revision != current["revision"]:
            raise Denied("stale or invalid revision")
        if revision == MAX_REVISION:
            raise Denied("revision exhausted")
        rec = copy.deepcopy(current)
        rec["revision"] += 1
        return rec

    def _unknown(self, reason):
        rec = self._begin(self._record["revision"])
        rec["state"] = "UNKNOWN"
        rec["unknown_reason"] = reason
        self._write(rec)

    @_public
    def snapshot(self):
        return self._snapshot()

    def _snapshot(self):
        self._verify_storage()
        if self._read() != self._record:
            self._poisoned = True
            raise StorageUnsafe("journal externally changed")
        return copy.deepcopy(self._record)

    @_public
    def reserve_generation(self, *, revision, generation, spec_digest, policy_digest, watchdog_ref):
        rec = self._begin(revision)
        if rec["state"] != "CLOSED" or rec["generation"] is not None:
            raise Denied("generation slot is occupied or closed UNKNOWN")
        if not _id(generation) or not _hex(spec_digest) or not _hex(policy_digest) or not _text(watchdog_ref):
            raise Denied("bounded immutable generation inputs required")
        rec["generation"] = {"id": generation, "spec_digest": spec_digest, "policy_digest": policy_digest,
            "watchdog_ref": watchdog_ref, "full_id": None, "observer_ref": None, "start_consumed": False,
            "attempt_id": None, "start_revision": None, "sealed": False, "terminal_observed": False,
            "last_observation": None, "observation_sequence": 0}
        rec["state"] = "CREATE_INTENT"
        self._write(rec)
        return self._snapshot()

    @_public
    def bind_created(self, *, revision, full_id):
        """Record candidate binding; does not verify actual runtime object or settings."""
        rec = self._begin(revision)
        if rec["state"] != "CREATE_INTENT" or not _hex(full_id):
            raise Denied("full 64-hex object id and unbound create intent required")
        rec["generation"]["full_id"] = full_id
        rec["state"] = "CREATED"
        self._write(rec)
        return self._snapshot()

    @_public
    def register_observer(self, *, revision, observer_ref):
        """Record trusted adapter's registration reference, not runtime proof."""
        rec = self._begin(revision)
        if rec["state"] != "CREATED" or rec["generation"]["observer_ref"] is not None or not _id(observer_ref):
            raise Denied("one prospective observer registration required")
        rec["generation"]["observer_ref"] = observer_ref
        self._write(rec)
        return self._snapshot()

    @_public
    def consume_start(self, *, revision):
        rec = self._begin(revision)
        g = rec["generation"]
        if rec["state"] != "CREATED" or g["start_consumed"] or g["observer_ref"] is None:
            raise Denied("start unavailable, already consumed, or observer missing")
        g["start_consumed"] = True
        g["attempt_id"] = uuid.uuid4().hex
        g["start_revision"] = rec["revision"]
        rec["state"] = "START_INTENT"
        self._write(rec)
        try:
            self._checkpoint("before_permit_return")
            self._verify_storage()
            if self._read() != self._record:
                raise StorageUnsafe("journal changed before permit return")
            return StartPermit(rec["journal_id"], rec["revision"], g["id"], g["spec_digest"], g["policy_digest"],
                rec["daemon"]["endpoint_ref"], rec["daemon"]["identity"], g["full_id"], g["attempt_id"],
                g["observer_ref"], g["watchdog_ref"])
        except BaseException:
            self._poisoned = True
            raise

    @_public
    def observe(self, *, revision, observation):
        """Conservative reducer of untrusted bounded observations. No retirement proof.

        Schema: kind, sequence, journal_id, generation, spec_digest, policy_digest,
        endpoint_ref, daemon_identity, full_id, attempt_id, start_revision, observer_ref.
        Exact duplicate last observation is idempotent. Reordering, gaps, mismatches,
        transport/error/continuity loss close UNKNOWN. EXIT_REPORTED never releases.
        """
        rec = self._begin(revision)
        g = rec["generation"]
        keys = {"kind", "sequence", "journal_id", "generation", "spec_digest", "policy_digest", "endpoint_ref",
                "daemon_identity", "full_id", "attempt_id", "start_revision", "observer_ref"}
        if not _exact_keys(observation, keys):
            raise Denied("bounded observation schema required")
        if (type(observation["kind"]) is not str or observation["kind"] not in KINDS
                or not _integer(observation["sequence"], 1)
                or not _integer(observation["start_revision"], 1)
                or not all(_text(observation[k]) for k in keys - {"kind", "sequence", "start_revision"})):
            raise Denied("invalid observation values")
        if g is None or not g["start_consumed"]:
            rec["state"], rec["unknown_reason"] = "UNKNOWN", "unexpected execution observation"
        else:
            expected = {"journal_id": rec["journal_id"], "generation": g["id"], "spec_digest": g["spec_digest"],
                "policy_digest": g["policy_digest"], "endpoint_ref": rec["daemon"]["endpoint_ref"],
                "daemon_identity": rec["daemon"]["identity"], "full_id": g["full_id"],
                "attempt_id": g["attempt_id"], "start_revision": g["start_revision"], "observer_ref": g["observer_ref"]}
            digest = hashlib.sha256(_canonical(observation)).hexdigest()
            if any(observation[k] != v for k, v in expected.items()):
                rec["state"], rec["unknown_reason"] = "UNKNOWN", "observation identity conflict"
            elif (observation["sequence"] == g["observation_sequence"]
                  and digest == g["last_observation"]):
                return self._snapshot()
            elif observation["sequence"] != g["observation_sequence"] + 1:
                rec["state"], rec["unknown_reason"] = "UNKNOWN", "observation order or continuity conflict"
            else:
                g["observation_sequence"], g["last_observation"] = observation["sequence"], digest
                kind = observation["kind"]
                if kind in {"START_RESPONSE_ERROR", "START_RESPONSE_LOST", "OBSERVER_LOST", "CONFLICT"}:
                    rec["state"], rec["unknown_reason"] = "UNKNOWN", "ambiguous or conflicting runtime observation"
                elif kind == "RUNNING_REPORTED" and (g["sealed"] or g["terminal_observed"]):
                    rec["state"], rec["unknown_reason"] = "UNKNOWN", "execution reported after terminal boundary"
                elif kind == "EXIT_REPORTED":
                    g["terminal_observed"] = True
                    if rec["state"] not in {"UNKNOWN", "SEALED"}:
                        rec["state"] = "RETIRING"
                elif rec["state"] == "START_INTENT":
                    rec["state"] = "STARTING"
        self._write(rec)
        return self._snapshot()

    @_public
    def seal(self, *, revision):
        """Permanent LOCAL terminal tombstone; no runtime-retirement claim or slot release."""
        rec = self._begin(revision)
        if rec["generation"] is None:
            raise Denied("no generation to seal")
        rec["generation"]["sealed"] = True
        if rec["state"] != "UNKNOWN":
            rec["state"] = "SEALED"
        self._write(rec)
        return self._snapshot()

    @_public
    def close(self):
        if self._closed:
            return
        if self._pid == os.getpid() and self._thread is not threading.current_thread():
            raise Denied("only owning thread may close this process session")
        # flock is shared across fork's open file description: never LOCK_UN in a child.
        # Closing only this process's copy cannot release a live parent's lock.
        # close(2) errors can be ambiguous. Detach first so a later close cannot
        # act on recycled descriptor numbers. Attempt each original fd only once.
        lock_fd, directory_fd = self._lock_fd, self._directory_fd
        self._lock_fd = self._directory_fd = None
        self._closed = True
        failure = None
        for fd in (lock_fd, directory_fd):
            try:
                os.close(fd)
            except OSError as exc:
                if failure is None:
                    failure = exc
        if failure is not None:
            raise failure

    def __enter__(self):
        self._owner()
        return self

    def __exit__(self, *_):
        self.close()

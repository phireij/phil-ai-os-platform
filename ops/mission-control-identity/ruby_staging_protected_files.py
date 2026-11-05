"""Default-off, startup-only mounted-file boundary for isolated Ruby staging.

Fixed paths: /run/secrets/ruby-staging/{config,secret}.json. A trusted launcher
must supply explicit numeric ownership expectations and an expected generation.
The provider must publish that complete immutable generation before startup and
must not write, replace, remount or rotate it while loading or serving. Construct
only in the final worker after fork; stop the old worker before a replacement.
This module does not establish those host/lifecycle conditions or load at import.

Descriptor checks bind reads to opened objects, not a prior pathname check.
Read-only mount flags describe this process's view, not other mounts or host
writers. Generation equality is not a transaction. O_NONBLOCK avoids FIFO-open
hangs, not regular-file I/O stalls or device-open effects; protected ancestors
and a trusted provider remain prerequisites. Runtime startup deadlines remain
required. Closing/dropping Python references does not guarantee secret erasure.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import stat
import time
from typing import Callable

from ruby_staging_app_factory import create_staging_application
from ruby_staging_http_app import StagingHTTPConfig, StagingRequestLimits

_GENERATION = re.compile(r"[0-9a-f]{32}", re.ASCII)
_CONFIG_BYTES = 16384
_SECRET_BYTES = 8192
_ERROR = "staging_protected_configuration_invalid"


class StagingProtectedConfigurationError(ValueError):
    """Fixed failure without credential, file contents or supplied identity."""


@dataclass(frozen=True)
class StagingFileOwnership:
    """Trusted startup policy, not values read from the configuration files.

The worker must run as reader_uid/reader_gid and both files must have that exact
ownership and mode 0400. Every directory must match directory_uid/directory_gid;
ancestors use 0755 or 0555, and the leaf is exactly 0555. IDs have no defaults.
These in-namespace comparisons do not establish host mappings, ACL/MAC policy,
capabilities or trust in whoever can publish the mount.
"""
    reader_uid: int
    reader_gid: int
    directory_uid: int
    directory_gid: int

    def validate(self) -> None:
        for value in (self.reader_uid, self.reader_gid, self.directory_uid, self.directory_gid):
            if type(value) is not int or not 0 <= value < 2**32 - 1:
                raise ValueError
        if self.reader_uid == 0:
            raise ValueError


def _snapshot(details) -> tuple:
    return (details.st_dev, details.st_ino, details.st_mode, details.st_uid,
            details.st_gid, details.st_nlink, details.st_size,
            details.st_mtime_ns, details.st_ctime_ns)


def _read_only(fd: int) -> None:
    if not os.fstatvfs(fd).f_flag & os.ST_RDONLY:
        raise ValueError


def _directory(fd: int, ownership: StagingFileOwnership, leaf: bool) -> None:
    details = os.fstat(fd)
    modes = {0o555} if leaf else {0o555, 0o755}
    if (not stat.S_ISDIR(details.st_mode) or details.st_uid != ownership.directory_uid
            or details.st_gid != ownership.directory_gid
            or stat.S_IMODE(details.st_mode) not in modes or os.get_inheritable(fd)):
        raise ValueError
    if leaf:
        _read_only(fd)


def _file(fd: int, ownership: StagingFileOwnership, maximum: int) -> tuple:
    details = os.fstat(fd)
    if (not stat.S_ISREG(details.st_mode) or details.st_uid != ownership.reader_uid
            or details.st_gid != ownership.reader_gid
            or stat.S_IMODE(details.st_mode) != 0o400 or details.st_nlink != 1
            or type(details.st_size) is not int or not 1 <= details.st_size <= maximum
            or os.get_inheritable(fd)):
        raise ValueError
    _read_only(fd)
    return _snapshot(details)


def _read(fd: int, maximum: int, expected_size: int) -> bytes:
    chunks = []
    size = 0
    while size <= maximum:
        chunk = os.read(fd, min(4096, maximum + 1 - size))
        if not chunk:
            if size != expected_size:
                raise ValueError
            return b"".join(chunks)
        chunks.append(chunk)
        size += len(chunk)
    raise ValueError


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError


def _document(raw: bytes, fields: set[str], generation: str) -> dict:
    value = json.loads(raw.decode("utf-8", errors="strict"),
                       object_pairs_hook=_pairs, parse_constant=_nonfinite)
    if (type(value) is not dict or set(value) != fields
            or type(value["version"]) is not int or value["version"] != 1
            or type(value["generation"]) is not str or value["generation"] != generation):
        raise ValueError
    return value


def _close_all(fds: list[int], suppress: bool) -> None:
    first = None
    for fd in reversed(fds):
        try:
            os.close(fd)
        except BaseException as failure:
            # Shutdown/control exceptions outrank earlier ordinary close errors.
            # If several controls occur, preserve the first one.
            if first is None or (isinstance(first, Exception) and not isinstance(failure, Exception)):
                first = failure
    fds.clear()
    # Never retry an uncertain close: its descriptor number may have been reused.
    if first is not None and not suppress:
        raise first


def _load(ownership: StagingFileOwnership, generation: str):
    for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK", "ST_RDONLY"):
        if type(getattr(os, name, None)) is not int or not getattr(os, name):
            raise ValueError
    if os.name != "posix" or not hasattr(os, "fstatvfs"):
        raise ValueError
    if (os.geteuid(), os.getegid()) != (ownership.reader_uid, ownership.reader_gid):
        raise ValueError
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    fds = []
    directories = []
    try:
        parent = os.open("/", directory_flags)
        fds.append(parent)
        _directory(parent, ownership, False)
        directories.append((parent, False))
        for component in ("run", "secrets", "ruby-staging"):
            parent = os.open(component, directory_flags, dir_fd=parent)
            fds.append(parent)
            leaf = component == "ruby-staging"
            _directory(parent, ownership, leaf)
            directories.append((parent, leaf))
        opened = []
        # Validate BOTH objects before reading either; keep all FDs until checks end.
        for name, maximum in (("config.json", _CONFIG_BYTES), ("secret.json", _SECRET_BYTES)):
            fd = os.open(name, file_flags, dir_fd=parent)
            fds.append(fd)
            opened.append((fd, maximum, _file(fd, ownership, maximum)))
        config_raw, secret_raw = [_read(fd, maximum, before[6]) for fd, maximum, before in opened]
        for fd, maximum, before in opened:
            if _file(fd, ownership, maximum) != before:
                raise ValueError
        for fd, leaf in directories:
            _directory(fd, ownership, leaf)
        if (os.geteuid(), os.getegid()) != (ownership.reader_uid, ownership.reader_gid):
            raise ValueError
        config = _document(config_raw, {"version", "generation", "config", "limits", "max_cache_seconds"}, generation)
        secret = _document(secret_raw, {"version", "generation", "client_secret"}, generation)
        if (type(config["config"]) is not dict or set(config["config"]) !=
                {"origin", "client_id", "owner_subject", "flow_seconds", "idle_seconds", "absolute_seconds", "capacity"}
                or type(config["limits"]) is not dict or set(config["limits"]) !=
                {"max_inflight_requests", "max_login_starts", "max_callback_attempts", "window_seconds"}):
            raise ValueError
        result = (StagingHTTPConfig(**config["config"]), StagingRequestLimits(**config["limits"]),
                  secret["client_secret"], config["max_cache_seconds"])
    except BaseException as primary:
        try:
            _close_all(fds, suppress=False)
        except BaseException as cleanup:
            if isinstance(primary, Exception) and not isinstance(cleanup, Exception):
                raise cleanup
        raise
    else:
        _close_all(fds, suppress=False)
        return result


def create_staging_application_from_files(*, enabled: bool = False,
        ownership: StagingFileOwnership | None = None, expected_generation: str | None = None,
        owner_policy=None,
        wall_clock: Callable[[], float] = time.time,
        monotonic_clock: Callable[[], float] = time.monotonic):
    """Read one immutable startup generation, close FDs, then call the factory.

No environment/CLI defaults, hot reload, activation, directory creation, chmod,
secret logging or listener. Ordinary failures are fixed and unchained. Control
exceptions propagate after best-effort cleanup. The returned app must be closed
by the separately approved final-worker lifecycle.
"""
    if enabled is False:
        return create_staging_application()
    try:
        if (enabled is not True or type(ownership) is not StagingFileOwnership
                or type(expected_generation) is not str or not _GENERATION.fullmatch(expected_generation)
                or not callable(wall_clock) or not callable(monotonic_clock)):
            raise ValueError
        ownership.validate()
        if owner_policy is not None:
            from ruby_staging_isolated_store import StagingOwnerStartupPolicy
            if type(owner_policy) is not StagingOwnerStartupPolicy:
                raise ValueError
            owner_policy.validate()
            if (owner_policy.generation != expected_generation or
                    (owner_policy.files.reader_uid, owner_policy.files.reader_gid) !=
                    (ownership.reader_uid, ownership.reader_gid)):
                raise ValueError
        if owner_policy is not None:
            from operations_hub.ruby_owner_owned_startup import preflight_owner_policy
            preflight_owner_policy(owner_policy)
        config, limits, secret, cache = _load(ownership, expected_generation)
        if owner_policy is not None:
            # Closed bundled selection, never a configured import/callback/class.
            from operations_hub.ruby_owner_owned_startup import create_owner_application
            return create_owner_application(policy=owner_policy, config=config, limits=limits,
                client_secret=secret, max_cache_seconds=cache, wall_clock=wall_clock,
                monotonic_clock=monotonic_clock)
        return create_staging_application(enabled=True, config=config, limits=limits,
            client_secret=secret, max_cache_seconds=cache, wall_clock=wall_clock,
            monotonic_clock=monotonic_clock)
    except Exception:
        raise StagingProtectedConfigurationError(_ERROR) from None

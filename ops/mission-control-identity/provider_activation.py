"""Explicit, protected MC-010 activation contract; disabled by default."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from provider_runtime import OpenAITransport, ProviderPolicy, ProviderRuntime


class ProviderConfigurationError(ValueError):
    """Fixed safe configuration error; no credential or request content."""


def _protected_file(variable: str, maximum: int) -> Path:
    raw = os.environ.get(variable, "")
    if not raw or not Path(raw).is_absolute():
        raise ProviderConfigurationError("provider_config_path_unset")
    path = Path(raw)
    try:
        details = path.lstat()
    except OSError:
        raise ProviderConfigurationError("provider_config_file_unavailable") from None
    if path.is_symlink() or not path.is_file() or (os.name != "nt" and details.st_mode & 0o077) or not 1 <= details.st_size <= maximum:
        raise ProviderConfigurationError("provider_config_file_invalid")
    return path


@dataclass(frozen=True)
class ProviderActivationConfig:
    api_key_file: Path
    policy_file: Path

    @classmethod
    def from_environment(cls) -> ProviderActivationConfig | None:
        enabled = os.environ.get("MISSION_CONTROL_OPENAI_ENABLED", "")
        dispatch = os.environ.get("MISSION_CONTROL_OPENAI_DISPATCH_ENABLED", "")
        if dispatch not in {"", "false", "true"} or (dispatch == "true" and enabled != "true"):
            raise ProviderConfigurationError("provider_dispatch_guard_invalid")
        if enabled in {"", "false"}:
            return None
        if enabled != "true":
            raise ProviderConfigurationError("provider_enabled_invalid")
        # Storage-preserving image preflight is always read-only and networkless,
        # even if the active container has provider activation configured.
        if os.environ.get("MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT") == "true":
            return None
        key = _protected_file("MISSION_CONTROL_OPENAI_API_KEY_FILE", 512)
        policy = _protected_file("MISSION_CONTROL_OPENAI_POLICY_FILE", 2048)
        if key == policy:
            raise ProviderConfigurationError("provider_config_paths_overlap")
        return cls(key, policy)

    def runtime(self, now: int) -> ProviderRuntime:
        try:
            key = self.api_key_file.read_text(encoding="ascii").strip()
            raw = json.loads(self.policy_file.read_text(encoding="ascii"))
        except (OSError, UnicodeError, ValueError):
            raise ProviderConfigurationError("provider_config_invalid") from None
        if not re.fullmatch(r"sk-[A-Za-z0-9_-]{20,500}", key):
            raise ProviderConfigurationError("provider_api_key_invalid")
        if not isinstance(raw, dict) or set(raw) != {"model", "input_rate", "output_rate", "valid_until"}:
            raise ProviderConfigurationError("provider_policy_invalid")
        # The current official standard price is $0.10/$0.50 per million for
        # gpt-6-luna. The 4x floor also covers the documented Fast and regional
        # premiums, plus a second input-count request. Re-review on expiry.
        if (raw["model"] != "gpt-6-luna" or type(raw["input_rate"]) is not int
                or type(raw["output_rate"]) is not int or type(raw["valid_until"]) is not int
                or raw["input_rate"] < 400_000 or raw["output_rate"] < 2_000_000
                or not now < raw["valid_until"] <= now + 7 * 86400):
            raise ProviderConfigurationError("provider_policy_unverified")
        policy = ProviderPolicy(**raw)
        transport = OpenAITransport(key)
        return ProviderRuntime(policy, transport.count_input, transport.send)


def acquire_provider_writer_lock(state_file: Path) -> int:
    """Hold one POSIX writer for the lifetime of the activated process."""
    if os.name != "posix":
        raise ProviderConfigurationError("provider_writer_lock_unavailable")
    import fcntl

    path = state_file.with_name("provider-writer.lock")
    if path.is_symlink():
        raise ProviderConfigurationError("provider_writer_lock_invalid")
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        details = os.fstat(descriptor)
        if details.st_mode & 0o077:
            raise ProviderConfigurationError("provider_writer_lock_invalid")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ProviderConfigurationError("provider_writer_lock_busy") from None
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


class ProviderResponseWorker:
    def __init__(self, store: Any, *, poll_seconds: int = 5,
                 clock: Callable[[], float] = time.time) -> None:
        self._store = store
        self._poll_seconds = poll_seconds
        self._clock = clock
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="mission-control-provider-response", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        # The caller must retain the single-writer lock until the in-flight
        # request has finished or the process has been killed.
        self._thread.join()

    def run_once(self) -> bool:
        return self._store.dispatch_one_response(now=int(self._clock()))

    def _run(self) -> None:
        while not self._stop.is_set():
            # A failed encrypted persistence operation ends the worker. It
            # cannot retry an outcome whose provider dispatch is uncertain.
            self.run_once()
            self._stop.wait(self._poll_seconds)

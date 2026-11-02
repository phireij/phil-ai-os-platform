"""Explicit, disposable-only bootstrap for Ruby synthetic review fixtures.

This module is an offline test harness.  It has no environment switch, listener,
runtime import, or route registration.  A caller must supply the exact opt-in
token and a pre-existing local storage scope; cleanup removes only the unique
run directory that this harness created.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from conversation_store import ConversationConfig, ConversationStore
from ruby_review_transport import RUBY_PROJECT, RubySyntheticReadBinding, build_disposable_synthetic_binding


HARNESS_OPT_IN = "ruby-synthetic-harness-v1"
_RUN_PREFIX = "ruby-synthetic-harness-"
_MARKER_NAME = ".ruby-synthetic-harness.json"
_MAX_OWNER_OR_ISSUER_LENGTH = 255
_AMBIENT_CORE_CONFIGURATION = (
    "MISSION_CONTROL_EVIDENCE_MANIFEST_FILE",
    "MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT",
)


class RubySyntheticHarnessError(ValueError):
    """Raised before any synthetic Core artifact is created."""


@dataclass
class DisposableRubySyntheticHarness:
    """Own one run-scoped Core fixture and nothing outside its run directory."""

    storage_scope: Path
    run_directory: Path
    config: ConversationConfig
    binding: RubySyntheticReadBinding
    owner_subject: str
    issuer: str
    _run_id: str
    _cleaned: bool = False

    @classmethod
    def create(
        cls,
        *,
        storage_scope: Path,
        opt_in: str | None,
        owner_subject: str,
        issuer: str,
    ) -> "DisposableRubySyntheticHarness":
        if opt_in != HARNESS_OPT_IN:
            raise RubySyntheticHarnessError("ruby_synthetic_harness_opt_in_required")
        if not _is_bounded_ascii(owner_subject):
            raise RubySyntheticHarnessError("ruby_synthetic_harness_owner_invalid")
        if not _is_bounded_ascii(issuer) or not issuer.startswith("https://"):
            raise RubySyntheticHarnessError("ruby_synthetic_harness_issuer_invalid")
        _reject_ambient_core_configuration()
        if not isinstance(storage_scope, Path) or storage_scope.is_symlink():
            raise RubySyntheticHarnessError("ruby_synthetic_harness_storage_scope_invalid")
        try:
            scope = storage_scope.resolve(strict=True)
        except OSError as exc:
            raise RubySyntheticHarnessError("ruby_synthetic_harness_storage_scope_invalid") from exc
        if not scope.is_dir():
            raise RubySyntheticHarnessError("ruby_synthetic_harness_storage_scope_invalid")

        run_id = secrets.token_hex(16)
        run_directory = Path(tempfile.mkdtemp(prefix=_RUN_PREFIX, dir=str(scope)))
        try:
            marker = run_directory / _MARKER_NAME
            marker.write_text(json.dumps({"run_id": run_id}, separators=(",", ":")), encoding="utf-8")
            key_file = run_directory / "harness.key"
            _write_private_file(key_file, secrets.token_hex(32).encode("ascii"))
            config = ConversationConfig(run_directory / "state.enc", run_directory / "ledger.enc", key_file)
            binding = build_disposable_synthetic_binding(config, owner_subject=owner_subject, issuer=issuer)
            return cls(scope, run_directory, config, binding, owner_subject, issuer, run_id)
        except Exception:
            shutil.rmtree(run_directory)
            raise

    def reopen_binding(self, *, owner_subject: str, issuer: str) -> RubySyntheticReadBinding:
        """Reopen this exact disposable Core without silently changing its owner."""
        self._require_owner_context(owner_subject=owner_subject, issuer=issuer)
        store = ConversationStore(
            self.config,
            self.issuer,
            self.owner_subject,
            ruby_review_projects=frozenset({RUBY_PROJECT}),
        )
        return RubySyntheticReadBinding(
            store=store,
            issuer=self.issuer,
            owner_subject=self.owner_subject,
            project_id=RUBY_PROJECT,
            records=self.binding.records,
        )

    def _require_owner_context(self, *, owner_subject: str, issuer: str) -> None:
        if (
            not _is_bounded_ascii(owner_subject)
            or not _is_bounded_ascii(issuer)
            or not issuer.startswith("https://")
        ):
            raise RubySyntheticHarnessError("ruby_synthetic_harness_owner_context_invalid")
        if not hmac.compare_digest(self.owner_subject, owner_subject) or not hmac.compare_digest(self.issuer, issuer):
            raise RubySyntheticHarnessError("ruby_synthetic_harness_owner_context_mismatch")

    def cleanup(self) -> None:
        """Remove only this harness's own marker-verified run directory."""
        if self._cleaned:
            return
        expected_parent = self.storage_scope.resolve(strict=True)
        if (
            self.run_directory.parent != expected_parent
            or not self.run_directory.name.startswith(_RUN_PREFIX)
            or self.run_directory.is_symlink()
        ):
            raise RubySyntheticHarnessError("ruby_synthetic_harness_cleanup_scope_invalid")
        marker = self.run_directory / _MARKER_NAME
        try:
            marker_value = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise RubySyntheticHarnessError("ruby_synthetic_harness_cleanup_marker_invalid") from exc
        if marker_value != {"run_id": self._run_id}:
            raise RubySyntheticHarnessError("ruby_synthetic_harness_cleanup_marker_invalid")
        shutil.rmtree(self.run_directory)
        self._cleaned = True

    def __enter__(self) -> "DisposableRubySyntheticHarness":
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.cleanup()


def _write_private_file(path: Path, value: bytes) -> None:
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(value)
    if os.name != "nt":
        os.chmod(path, 0o600)


def _is_bounded_ascii(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= _MAX_OWNER_OR_ISSUER_LENGTH
        and value.isascii()
        and all("!" <= character <= "~" for character in value)
    )


def _reject_ambient_core_configuration() -> None:
    if any(os.environ.get(variable, "") for variable in _AMBIENT_CORE_CONFIGURATION):
        raise RubySyntheticHarnessError("ruby_synthetic_harness_ambient_core_configuration_forbidden")

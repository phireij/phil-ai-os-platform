from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .normalizer import SUPPORTED_SOURCES, NormalizationError


class ChannelAdapterError(RuntimeError):
    def __init__(self, source: str, code: str, retryable: bool, message: str):
        super().__init__(message)
        self.source = source
        self.code = code
        self.retryable = retryable
        self.message = message

    def to_envelope(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "error_code": self.code,
            "retryable": self.retryable,
            "message": self.message,
            "authority_effect": "none",
            "mutation_authorized": False,
        }


class IngestionAdapter(Protocol):
    source: str

    def pull_fixture(self) -> dict[str, Any]: ...


@dataclass
class MockChannelAdapter:
    source: str
    fixture: dict[str, Any]
    fail_code: str | None = None
    retryable_failure: bool = False

    def __post_init__(self) -> None:
        if self.source not in SUPPORTED_SOURCES:
            raise NormalizationError(f"unsupported adapter source: {self.source}")
        if self.fixture.get("fixture_only") is not True:
            raise NormalizationError("mock adapter accepts fixture_only payloads")
        if self.fixture.get("source") != self.source:
            raise NormalizationError("adapter source must match fixture source")

    def pull_fixture(self) -> dict[str, Any]:
        if self.fail_code:
            raise ChannelAdapterError(
                source=self.source,
                code=self.fail_code,
                retryable=self.retryable_failure,
                message="synthetic adapter failure",
            )
        return dict(self.fixture)


def retry_decision(error: ChannelAdapterError, attempt: int, max_attempts: int = 3) -> dict[str, Any]:
    if attempt < 1 or max_attempts < 1:
        raise ValueError("attempt values must be positive")
    should_retry = error.retryable and attempt < max_attempts
    return {
        "retry": should_retry,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "reason": "transient_adapter_failure" if should_retry else "stop",
        "authority_effect": "none",
        "mutation_authorized": False,
    }

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .retry import retry_decision


class HTTPStatusFailure(RuntimeError):
    def __init__(self, status_code: int, message: str | None = None) -> None:
        self.status_code = int(status_code)
        super().__init__(message or f"injected HTTP failure: {status_code}")


@dataclass(frozen=True)
class RetryExecutionResult:
    value: Any
    attempts: int
    retry_delays: tuple[float, ...]


class FailureInjectingTransport:
    """Test-only wrapper that injects configured HTTP failures before delegating."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self._failures: dict[tuple[str, str], list[int]] = {}

    def queue_failure(self, method: str, path: str, status_code: int) -> None:
        key = (method.upper(), path)
        self._failures.setdefault(key, []).append(int(status_code))

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> Any:
        key = (method.upper(), path)
        queued = self._failures.get(key, [])
        if queued:
            status_code = queued.pop(0)
            raise HTTPStatusFailure(status_code)
        return self.inner.request(method, path, params=params, json_body=json_body)


def execute_with_retry(
    operation: Callable[[], Any],
    *,
    max_attempts: int = 4,
) -> RetryExecutionResult:
    """Execute a local/injected operation using the pure retry policy.

    No sleeping is performed in Sprint 3. Delays are returned as a plan so tests
    can verify policy without creating background work or live network behavior.
    """
    retry_delays: list[float] = []
    attempt = 1
    while True:
        try:
            return RetryExecutionResult(
                value=operation(),
                attempts=attempt,
                retry_delays=tuple(retry_delays),
            )
        except HTTPStatusFailure as exc:
            decision = retry_decision(exc.status_code, attempt, max_attempts=max_attempts)
            if not decision.retry:
                raise
            retry_delays.append(decision.delay_seconds)
            attempt += 1

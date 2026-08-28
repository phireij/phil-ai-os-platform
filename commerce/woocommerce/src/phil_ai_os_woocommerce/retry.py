from __future__ import annotations

from dataclasses import dataclass


RETRYABLE_HTTP_STATUS = frozenset({408, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    delay_seconds: float
    reason: str


def retry_decision(status_code: int, attempt: int, *, max_attempts: int = 4) -> RetryDecision:
    if attempt < 1:
        raise ValueError("attempt is 1-based")
    if attempt >= max_attempts:
        return RetryDecision(False, 0.0, "attempt_limit")
    if status_code not in RETRYABLE_HTTP_STATUS:
        return RetryDecision(False, 0.0, "non_retryable_status")
    # Pure calculation only; the Sprint 3 foundation never sleeps or calls a network.
    delay = min(8.0, 0.5 * (2 ** (attempt - 1)))
    return RetryDecision(True, delay, "transient_http_status")

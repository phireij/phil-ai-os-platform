from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .reconciliation import ReconciliationResult


@dataclass(frozen=True)
class CommerceSyncAuditEvent:
    correlation_id: str
    entity_type: str
    entity_key: str
    action: str
    idempotency_key: str
    remote_id: int | None
    before_fingerprint: str | None
    after_fingerprint: str
    observed_at: str
    authority_effect: str = "none"

    @classmethod
    def from_result(
        cls,
        result: ReconciliationResult,
        *,
        correlation_id: str,
        entity_type: str,
    ) -> "CommerceSyncAuditEvent":
        if not correlation_id.strip():
            raise ValueError("correlation_id is required")
        return cls(
            correlation_id=correlation_id,
            entity_type=entity_type,
            entity_key=result.entity_key,
            action=result.action,
            idempotency_key=result.idempotency_key,
            remote_id=result.remote_id,
            before_fingerprint=result.before_fingerprint,
            after_fingerprint=result.after_fingerprint,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

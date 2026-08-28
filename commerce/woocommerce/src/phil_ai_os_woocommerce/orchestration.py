from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .audit import CommerceSyncAuditEvent, MemoryAuditSink
from .reconciliation import ReconciliationResult


@dataclass(frozen=True)
class AuditedReconciliation:
    result: ReconciliationResult
    audit_event: CommerceSyncAuditEvent


def reconcile_with_audit(
    operation: Callable[[], ReconciliationResult],
    *,
    correlation_id: str,
    entity_type: str,
    audit_sink: MemoryAuditSink,
) -> AuditedReconciliation:
    """Run one already-bounded reconciliation and emit a no-authority audit event.

    This helper introduces no transport or mutation authority. The supplied
    operation retains its own fail-closed adapter boundary, and the in-memory
    audit sink independently rejects authority-bearing audit events.
    """
    if not correlation_id.strip():
        raise ValueError("correlation_id is required")
    if entity_type not in {"product", "category", "inventory", "media"}:
        raise ValueError(f"unsupported commerce entity_type: {entity_type}")

    result = operation()
    event = CommerceSyncAuditEvent.from_result(
        result,
        correlation_id=correlation_id,
        entity_type=entity_type,
    )
    audit_sink.emit(event)
    return AuditedReconciliation(result=result, audit_event=event)

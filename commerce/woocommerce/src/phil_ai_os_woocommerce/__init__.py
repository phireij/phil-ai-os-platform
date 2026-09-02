"""Phil AI OS WooCommerce foundation package.

Sprint 3 boundary: this package contains contracts, reconciliation logic, and
mock/injected adapter behavior only. It intentionally ships no live WooCommerce
network transport or production credentials.
"""

from .adapter import (
    MockWooCommerceTransport,
    ProductionConnectivityBlocked,
    WooCommerceAdapter,
)
from .audit import CommerceSyncAuditEvent, MemoryAuditSink
from .auth import (
    AuthenticationBoundary,
    CredentialBoundaryError,
    CredentialReference,
    CredentialReferenceProvider,
    NoCredentialsProvider,
    SPRINT3_AUTH_BOUNDARY,
)
from .category_plan import (
    CategoryHierarchyError,
    CategoryPlanItem,
    plan_category_hierarchy,
    project_category_payload,
)
from .inventory_guard import (
    InventoryConflictError,
    InventoryRevisionState,
    MemoryInventoryRevisionStore,
    StaleInventoryRevision,
)
from .localization import (
    DEFAULT_LOCALIZATION_POLICY,
    LocalizationPolicy,
    SUPPORTED_LOCALES,
    project_localized,
)
from .media_plan import (
    MediaPlanError,
    MediaReconciliationPlan,
    build_product_media_plan,
    plan_media_reconciliation,
)
from .models import (
    CategoryRecord,
    FulfillmentProfile,
    InventoryRecord,
    LocalizedText,
    MediaRecord,
    ProductRecord,
)
from .orchestration import AuditedReconciliation, reconcile_with_audit
from .resilience import (
    FailureInjectingTransport,
    HTTPStatusFailure,
    RetryExecutionResult,
    execute_with_retry,
)
from .retry import RetryDecision, retry_decision
from .reconciliation import MemoryIdempotencyStore, ReconciliationResult
from .rollback import MockCommerceSnapshot, MockRollbackError, capture_mock_snapshot, restore_mock_snapshot

__all__ = [
    "AuditedReconciliation",
    "AuthenticationBoundary",
    "CategoryHierarchyError",
    "CategoryPlanItem",
    "CategoryRecord",
    "CommerceSyncAuditEvent",
    "CredentialBoundaryError",
    "CredentialReference",
    "CredentialReferenceProvider",
    "DEFAULT_LOCALIZATION_POLICY",
    "FailureInjectingTransport",
    "FulfillmentProfile",
    "HTTPStatusFailure",
    "InventoryConflictError",
    "InventoryRecord",
    "InventoryRevisionState",
    "LocalizationPolicy",
    "LocalizedText",
    "MediaPlanError",
    "MediaReconciliationPlan",
    "MediaRecord",
    "MemoryAuditSink",
    "MemoryIdempotencyStore",
    "MemoryInventoryRevisionStore",
    "MockCommerceSnapshot",
    "MockRollbackError",
    "MockWooCommerceTransport",
    "NoCredentialsProvider",
    "ProductRecord",
    "ProductionConnectivityBlocked",
    "ReconciliationResult",
    "RetryDecision",
    "RetryExecutionResult",
    "SPRINT3_AUTH_BOUNDARY",
    "SUPPORTED_LOCALES",
    "StaleInventoryRevision",
    "WooCommerceAdapter",
    "build_product_media_plan",
    "capture_mock_snapshot",
    "execute_with_retry",
    "plan_category_hierarchy",
    "plan_media_reconciliation",
    "project_category_payload",
    "project_localized",
    "reconcile_with_audit",
    "restore_mock_snapshot",
    "retry_decision",
]

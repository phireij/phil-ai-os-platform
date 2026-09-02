"""Phil AI OS WooCommerce foundation and production-activation contracts.

The package remains fail-closed by default. The production wc/v3 transport is
present only as an explicitly enabled runtime capability: it resolves credentials
from opaque external references, blocks mutations independently, and does not
grant production readiness or launch authority by itself.
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
from .catalog_readiness import CatalogTaxReadiness, evaluate_catalog_tax_readiness
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
from .production_transport import (
    NoWooCommerceSecretResolver,
    ProductionWooCommerceConfig,
    ProductionWooCommerceTransport,
    ResolvedWooCommerceCredentials,
    WooCommerceActivationPreflight,
    WooCommerceHttpClient,
    WooCommerceSecretResolver,
)
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
    "CatalogTaxReadiness",
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
    "NoWooCommerceSecretResolver",
    "ProductRecord",
    "ProductionConnectivityBlocked",
    "ProductionWooCommerceConfig",
    "ProductionWooCommerceTransport",
    "ReconciliationResult",
    "ResolvedWooCommerceCredentials",
    "RetryDecision",
    "RetryExecutionResult",
    "SPRINT3_AUTH_BOUNDARY",
    "SUPPORTED_LOCALES",
    "StaleInventoryRevision",
    "WooCommerceActivationPreflight",
    "WooCommerceAdapter",
    "WooCommerceHttpClient",
    "WooCommerceSecretResolver",
    "build_product_media_plan",
    "capture_mock_snapshot",
    "execute_with_retry",
    "evaluate_catalog_tax_readiness",
    "plan_category_hierarchy",
    "plan_media_reconciliation",
    "project_category_payload",
    "project_localized",
    "reconcile_with_audit",
    "restore_mock_snapshot",
    "retry_decision",
]

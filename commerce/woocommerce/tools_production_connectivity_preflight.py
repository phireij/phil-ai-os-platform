from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from phil_ai_os_woocommerce.auth import CredentialReference
from phil_ai_os_woocommerce.production_transport import (
    ProductionWooCommerceConfig,
    ProductionWooCommerceTransport,
    ResolvedWooCommerceCredentials,
)


class EnvironmentSecretResolver:
    """Resolve WooCommerce credentials from process environment only.

    The opaque reference is validated but never interpreted as secret material.
    No credential value is printed or persisted.
    """

    def resolve(self, secret_ref: str) -> ResolvedWooCommerceCredentials:
        if secret_ref != "env://ruby/woocommerce/production-readonly":
            raise RuntimeError("unexpected WooCommerce secret reference")
        consumer_key = os.environ.get("RUBY_WOO_PRODUCTION_CONSUMER_KEY", "")
        consumer_secret = os.environ.get("RUBY_WOO_PRODUCTION_CONSUMER_SECRET", "")
        return ResolvedWooCommerceCredentials(consumer_key, consumer_secret)


def main() -> int:
    base_url = os.environ.get("RUBY_WOO_PRODUCTION_BASE_URL", "").strip()
    if not base_url:
        raise SystemExit("PHIL_AI_OS_WOO_PRODUCTION_PREFLIGHT_BLOCKED: base_url_missing")

    reference = CredentialReference(
        identity_alias="ruby-woo-production-readonly",
        secret_ref="env://ruby/woocommerce/production-readonly",
        access_mode="read_only",
        environment="production",
    )
    transport = ProductionWooCommerceTransport(
        ProductionWooCommerceConfig(
            base_url=base_url,
            credential_reference=reference,
            enabled=True,
            allow_mutations=False,
            timeout_seconds=10.0,
        ),
        secret_resolver=EnvironmentSecretResolver(),
    )

    # Intentionally read-only. A one-item product query proves wc/v3 routing and
    # credential validity without changing catalog, tax, orders or settings.
    payload = transport.request("GET", "/products", params={"per_page": "1"})
    if not isinstance(payload, list):
        raise SystemExit("PHIL_AI_OS_WOO_PRODUCTION_PREFLIGHT_FAILED: unexpected_products_response")

    print(
        "PHIL_AI_OS_WOO_PRODUCTION_READONLY_PREFLIGHT_GREEN "
        "wc_v3=true identity=true mutation=false catalog_write=false tax_write=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

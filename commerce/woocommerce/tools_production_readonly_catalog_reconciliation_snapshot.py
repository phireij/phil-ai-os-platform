from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from phil_ai_os_woocommerce.auth import CredentialReference
from phil_ai_os_woocommerce.production_transport import (
    ProductionWooCommerceConfig,
    ProductionWooCommerceTransport,
    ResolvedWooCommerceCredentials,
)
from phil_ai_os_woocommerce.readonly_catalog_snapshot import (
    collect_catalog_reconciliation_snapshot,
)


class EnvironmentReadOnlySecretResolver:
    def resolve(self, secret_ref: str) -> ResolvedWooCommerceCredentials:
        if secret_ref != "env://ruby/woocommerce/production-readonly":
            raise RuntimeError("unexpected WooCommerce secret reference")
        return ResolvedWooCommerceCredentials(
            os.environ.get("RUBY_WOO_PRODUCTION_CONSUMER_KEY", ""),
            os.environ.get("RUBY_WOO_PRODUCTION_CONSUMER_SECRET", ""),
        )


def build_transport() -> ProductionWooCommerceTransport:
    base_url = os.environ.get("RUBY_WOO_PRODUCTION_BASE_URL", "").strip()
    if not base_url:
        raise SystemExit(
            "PHIL_AI_OS_WOO_READONLY_RECONCILIATION_SNAPSHOT_BLOCKED: base_url_missing"
        )

    reference = CredentialReference(
        identity_alias="ruby-woo-production-readonly",
        secret_ref="env://ruby/woocommerce/production-readonly",
        access_mode="read_only",
        environment="production",
    )
    return ProductionWooCommerceTransport(
        ProductionWooCommerceConfig(
            base_url=base_url,
            credential_reference=reference,
            enabled=True,
            allow_mutations=False,
            timeout_seconds=10.0,
        ),
        secret_resolver=EnvironmentReadOnlySecretResolver(),
    )


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1:
        raise SystemExit(
            "usage: tools_production_readonly_catalog_reconciliation_snapshot.py OUTPUT_JSON"
        )

    output_path = Path(args[0])
    snapshot = collect_catalog_reconciliation_snapshot(build_transport())
    rendered = snapshot.as_dict()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(rendered, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    variable_products = sum(1 for item in snapshot.products if item.get("type") == "variable")
    variations = sum(len(item.get("variations", [])) for item in snapshot.products)
    print(
        "PHIL_AI_OS_WOO_PRODUCTION_READONLY_RECONCILIATION_SNAPSHOT_GREEN "
        f"products={len(snapshot.products)} variable_products={variable_products} "
        f"variations={variations} network_read_only=true mutation=false "
        "production_publish=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
from phil_ai_os_woocommerce.readonly_checkout_snapshot import collect_checkout_snapshot


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
        raise SystemExit("PHIL_AI_OS_WOO_READONLY_CHECKOUT_SNAPSHOT_BLOCKED: base_url_missing")

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
        raise SystemExit("usage: tools_production_readonly_checkout_snapshot.py OUTPUT_JSON")

    output_path = Path(args[0])
    snapshot = collect_checkout_snapshot(build_transport())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    enabled = [gateway.gateway_id for gateway in snapshot.gateways if gateway.enabled]
    print(
        "PHIL_AI_OS_WOO_PRODUCTION_READONLY_CHECKOUT_SNAPSHOT_GREEN "
        f"gateways={len(snapshot.gateways)} enabled={len(enabled)} "
        "network_read_only=true mutation=false payment_execution=false production_publish=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

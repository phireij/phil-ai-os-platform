from __future__ import annotations

import base64
import unittest

from phil_ai_os_woocommerce.adapter import ProductionConnectivityBlocked
from phil_ai_os_woocommerce.auth import CredentialReference
from phil_ai_os_woocommerce.production_transport import (
    ProductionWooCommerceConfig,
    ProductionWooCommerceTransport,
    ResolvedWooCommerceCredentials,
    WooCommerceActivationPreflight,
)


class FakeResolver:
    def __init__(self) -> None:
        self.refs: list[str] = []

    def resolve(self, secret_ref: str) -> ResolvedWooCommerceCredentials:
        self.refs.append(secret_ref)
        return ResolvedWooCommerceCredentials("ck_test_runtime_only", "cs_test_runtime_only")


class FakeHttpClient:
    def __init__(self, status: int = 200, payload=None) -> None:
        self.status = status
        self.payload = [] if payload is None else payload
        self.calls: list[dict[str, object]] = []

    def request(self, method, url, *, headers, body, timeout_seconds):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "body": body,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.status, self.payload


def production_ref(access_mode: str = "read_only") -> CredentialReference:
    return CredentialReference(
        identity_alias="ruby-woo-production",
        secret_ref="secret://ruby/woocommerce/production",
        access_mode=access_mode,
        environment="production",
    )


class ProductionTransportTests(unittest.TestCase):
    def test_disabled_transport_never_resolves_secret_or_calls_network(self):
        resolver = FakeResolver()
        http = FakeHttpClient()
        transport = ProductionWooCommerceTransport(
            ProductionWooCommerceConfig(
                base_url="https://store.example.test",
                credential_reference=production_ref(),
            ),
            secret_resolver=resolver,
            http_client=http,
        )
        with self.assertRaises(ProductionConnectivityBlocked):
            transport.request("GET", "/products")
        self.assertEqual(resolver.refs, [])
        self.assertEqual(http.calls, [])

    def test_production_base_url_must_use_https(self):
        transport = ProductionWooCommerceTransport(
            ProductionWooCommerceConfig(
                base_url="http://store.example.test",
                credential_reference=production_ref(),
                enabled=True,
            ),
            secret_resolver=FakeResolver(),
            http_client=FakeHttpClient(),
        )
        with self.assertRaises(ProductionConnectivityBlocked):
            transport.request("GET", "/products")

    def test_enabled_read_uses_wc_v3_and_runtime_basic_auth(self):
        resolver = FakeResolver()
        http = FakeHttpClient(payload=[{"id": 7, "sku": "SKU-7"}])
        transport = ProductionWooCommerceTransport(
            ProductionWooCommerceConfig(
                base_url="https://store.example.test",
                credential_reference=production_ref(),
                enabled=True,
            ),
            secret_resolver=resolver,
            http_client=http,
        )
        result = transport.request("GET", "/products", params={"sku": "SKU-7"})
        self.assertEqual(result[0]["id"], 7)
        self.assertEqual(resolver.refs, ["secret://ruby/woocommerce/production"])
        call = http.calls[0]
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["url"], "https://store.example.test/wp-json/wc/v3/products?sku=SKU-7")
        expected = base64.b64encode(b"ck_test_runtime_only:cs_test_runtime_only").decode("ascii")
        self.assertEqual(call["headers"]["Authorization"], f"Basic {expected}")

    def test_mutation_is_blocked_without_explicit_mutation_enablement(self):
        resolver = FakeResolver()
        http = FakeHttpClient(payload={"id": 8})
        transport = ProductionWooCommerceTransport(
            ProductionWooCommerceConfig(
                base_url="https://store.example.test",
                credential_reference=production_ref(),
                enabled=True,
                allow_mutations=False,
            ),
            secret_resolver=resolver,
            http_client=http,
        )
        with self.assertRaises(ProductionConnectivityBlocked):
            transport.request("POST", "/products", json_body={"name": "blocked"})
        self.assertEqual(resolver.refs, [])
        self.assertEqual(http.calls, [])

    def test_mutation_requires_read_write_reference(self):
        transport = ProductionWooCommerceTransport(
            ProductionWooCommerceConfig(
                base_url="https://store.example.test",
                credential_reference=production_ref("read_only"),
                enabled=True,
                allow_mutations=True,
            ),
            secret_resolver=FakeResolver(),
            http_client=FakeHttpClient(),
        )
        with self.assertRaises(ProductionConnectivityBlocked):
            transport.request("POST", "/products", json_body={"name": "blocked"})

    def test_provider_http_failure_fails_closed(self):
        transport = ProductionWooCommerceTransport(
            ProductionWooCommerceConfig(
                base_url="https://store.example.test",
                credential_reference=production_ref(),
                enabled=True,
            ),
            secret_resolver=FakeResolver(),
            http_client=FakeHttpClient(status=401, payload={"code": "unauthorized"}),
        )
        with self.assertRaises(ProductionConnectivityBlocked):
            transport.request("GET", "/products")

    def test_preflight_keeps_mutation_blocked_by_catalog_tax_legal_and_recovery(self):
        preflight = WooCommerceActivationPreflight(
            ceo_scope_approved=True,
            production_identity_ready=False,
            approved_catalog_ready=False,
            tax_ready=False,
            checkout_legal_sync_ready=False,
            recovery_fresh=False,
        )
        self.assertFalse(preflight.read_connectivity_ready)
        self.assertFalse(preflight.mutation_ready)
        self.assertEqual(
            preflight.mutation_blockers,
            (
                "production_identity_not_ready",
                "approved_catalog_not_ready",
                "tax_not_ready",
                "checkout_legal_sync_not_ready",
                "recovery_not_fresh",
            ),
        )

    def test_preflight_can_become_ready_only_when_every_gate_is_true(self):
        preflight = WooCommerceActivationPreflight(
            ceo_scope_approved=True,
            production_identity_ready=True,
            approved_catalog_ready=True,
            tax_ready=True,
            checkout_legal_sync_ready=True,
            recovery_fresh=True,
        )
        self.assertTrue(preflight.read_connectivity_ready)
        self.assertTrue(preflight.mutation_ready)
        self.assertEqual(preflight.mutation_blockers, ())


if __name__ == "__main__":
    unittest.main()

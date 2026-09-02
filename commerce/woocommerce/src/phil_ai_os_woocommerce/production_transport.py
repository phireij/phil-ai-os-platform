from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib import parse, request

from .adapter import ProductionConnectivityBlocked
from .auth import CredentialReference


@dataclass(frozen=True)
class ResolvedWooCommerceCredentials:
    consumer_key: str
    consumer_secret: str

    def validate(self) -> None:
        if not self.consumer_key.startswith("ck_"):
            raise ProductionConnectivityBlocked("resolved WooCommerce consumer key is invalid")
        if not self.consumer_secret.startswith("cs_"):
            raise ProductionConnectivityBlocked("resolved WooCommerce consumer secret is invalid")


class WooCommerceSecretResolver(Protocol):
    def resolve(self, secret_ref: str) -> ResolvedWooCommerceCredentials: ...


class NoWooCommerceSecretResolver:
    def resolve(self, secret_ref: str) -> ResolvedWooCommerceCredentials:
        raise ProductionConnectivityBlocked(
            f"WooCommerce secret resolution is not configured for opaque reference: {secret_ref}"
        )


class WooCommerceHttpClient(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> tuple[int, Any]: ...


class UrllibWooCommerceHttpClient:
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> tuple[int, Any]:
        req = request.Request(url, data=body, headers=dict(headers), method=method)
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                payload = json.loads(raw) if raw else None
                return int(response.status), payload
        except Exception as exc:
            raise ProductionConnectivityBlocked("WooCommerce production request failed safely") from exc


@dataclass(frozen=True)
class ProductionWooCommerceConfig:
    base_url: str
    credential_reference: CredentialReference
    enabled: bool = False
    allow_mutations: bool = False
    timeout_seconds: float = 10.0

    def validate(self) -> None:
        if not self.base_url.startswith("https://"):
            raise ProductionConnectivityBlocked("production WooCommerce base_url must use HTTPS")
        if self.credential_reference.environment != "production":
            raise ProductionConnectivityBlocked("production WooCommerce credential reference must target production")
        if self.allow_mutations and self.credential_reference.access_mode != "read_write":
            raise ProductionConnectivityBlocked("WooCommerce mutations require a read_write credential reference")
        if self.timeout_seconds <= 0:
            raise ProductionConnectivityBlocked("WooCommerce timeout_seconds must be positive")


@dataclass(frozen=True)
class WooCommerceActivationPreflight:
    ceo_scope_approved: bool
    production_identity_ready: bool
    approved_catalog_ready: bool
    tax_ready: bool
    checkout_legal_sync_ready: bool
    recovery_fresh: bool

    @property
    def read_connectivity_ready(self) -> bool:
        return self.ceo_scope_approved and self.production_identity_ready

    @property
    def mutation_ready(self) -> bool:
        return all(
            (
                self.read_connectivity_ready,
                self.approved_catalog_ready,
                self.tax_ready,
                self.checkout_legal_sync_ready,
                self.recovery_fresh,
            )
        )

    @property
    def mutation_blockers(self) -> tuple[str, ...]:
        blockers: list[str] = []
        if not self.ceo_scope_approved:
            blockers.append("ceo_scope_approval_missing")
        if not self.production_identity_ready:
            blockers.append("production_identity_not_ready")
        if not self.approved_catalog_ready:
            blockers.append("approved_catalog_not_ready")
        if not self.tax_ready:
            blockers.append("tax_not_ready")
        if not self.checkout_legal_sync_ready:
            blockers.append("checkout_legal_sync_not_ready")
        if not self.recovery_fresh:
            blockers.append("recovery_not_fresh")
        return tuple(blockers)


class ProductionWooCommerceTransport:
    """Fail-closed WooCommerce wc/v3 network transport.

    The transport is inert unless `enabled=True`. Credential material is resolved
    only at request time from an opaque production reference and is never stored in
    repository configuration. Mutating HTTP methods also require
    `allow_mutations=True` and a read_write credential reference.
    """

    def __init__(
        self,
        config: ProductionWooCommerceConfig,
        *,
        secret_resolver: WooCommerceSecretResolver | None = None,
        http_client: WooCommerceHttpClient | None = None,
    ) -> None:
        self.config = config
        self.secret_resolver = secret_resolver or NoWooCommerceSecretResolver()
        self.http_client = http_client or UrllibWooCommerceHttpClient()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> Any:
        self.config.validate()
        if not self.config.enabled:
            raise ProductionConnectivityBlocked("WooCommerce production transport is disabled")

        method = method.upper()
        if method not in {"GET", "POST", "PUT"}:
            raise ProductionConnectivityBlocked(f"unsupported WooCommerce production method: {method}")
        if method in {"POST", "PUT"} and not self.config.allow_mutations:
            raise ProductionConnectivityBlocked("WooCommerce production mutations are disabled")
        if not path.startswith("/") or ".." in path:
            raise ProductionConnectivityBlocked("invalid WooCommerce API path")

        credentials = self.secret_resolver.resolve(self.config.credential_reference.secret_ref)
        credentials.validate()
        basic = base64.b64encode(
            f"{credentials.consumer_key}:{credentials.consumer_secret}".encode("utf-8")
        ).decode("ascii")

        query = parse.urlencode(dict(params or {}))
        url = f"{self.config.base_url.rstrip('/')}/wp-json/wc/v3{path}"
        if query:
            url = f"{url}?{query}"

        headers = {
            "Authorization": f"Basic {basic}",
            "Accept": "application/json",
            "User-Agent": "phil-ai-os-platform/woocommerce-production-transport",
        }
        body: bytes | None = None
        if json_body is not None:
            body = json.dumps(dict(json_body), separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"

        status_code, payload = self.http_client.request(
            method,
            url,
            headers=headers,
            body=body,
            timeout_seconds=self.config.timeout_seconds,
        )
        if status_code < 200 or status_code >= 300:
            raise ProductionConnectivityBlocked(
                f"WooCommerce production request failed with HTTP {status_code}"
            )
        return payload

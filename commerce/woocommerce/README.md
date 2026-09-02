# Sprint 3 — WooCommerce Foundation

This directory contains the bounded WooCommerce commerce foundation plus the
CEO-approved Sprint 7 production-activation transport contract. Production
connectivity and mutations remain fail-closed at runtime until their independent
readiness requirements are satisfied.

The catalog/tax intake gate in `catalog_readiness.py` prepares the current
pre-production decision work without authorizing a WooCommerce change. Its
template keeps product and tax decisions explicitly pending, evaluates catalog
and tax readiness separately, and always returns both mutation and production
publish authority as false.

## Approved deployment boundary

- Ruby's customer-facing WordPress + WooCommerce production site will live on Hostinger managed web hosting.
- The retained public customer domain is `https://www.rubyscakedelights.shop/`.
- Phil AI OS, Mission Control, Hermes/agents, reconciliation, audit, CX, and Operations remain on the Hostinger VPS.
- The current Hostinger Website Builder site is reference-only. Store information, contact information, and policies may be reviewed for migration after verification. Its test products and categories are explicitly excluded.

The public domain above is architecture/migration planning data only. It is not
a configured active WooCommerce API endpoint in repository state.

## Safety boundary

- No production WooCommerce consumer key/secret is stored in this repository.
- Production credentials are accepted only through an opaque `CredentialReference` and resolved at request time by an injected secret resolver.
- `ProductionWooCommerceTransport` is disabled by default and cannot resolve a secret or make a network call until explicitly enabled.
- Production mutations have a separate `allow_mutations` gate and require a `read_write` production credential reference.
- `WooCommerceActivationPreflight` keeps mutation readiness false until CEO scope approval, production identity, approved catalog, tax, checkout/legal synchronization and fresh recovery are all ready.
- The production transport only accepts HTTPS and the WooCommerce `wc/v3` surface; provider/HTTP failures fail closed.
- The CEO approved the production-activation scope on 2026-09-02, but approval does not override missing catalog/tax evidence, credentials, recovery freshness or launch acceptance.

## Authentication boundary

`auth.py` defines the opaque credential-reference contract. Raw consumer-key or
consumer-secret material is rejected when supplied as the reference itself.
`production_transport.py` resolves actual credentials only at runtime through an
injected resolver; the default resolver always fails closed. No secret values are
committed to repository configuration or fixtures.

The historical `SPRINT3_AUTH_BOUNDARY` remains the inert Sprint 3 baseline. The
Sprint 7 production transport is a later, separately gated capability and does
not mutate that historical baseline object.

## Contract and reconciliation strategy

Phil AI OS owns a bilingual canonical commerce contract. WooCommerce is treated as an integration projection, not as an implied governance authority. Bilingual canonical fields require both `en` and `ja`; locale-specific WooCommerce payloads are generated deterministically.

Japanese slugs are explicit contract data, not automatically transliterated. This prevents unstable slug changes across libraries or deployments.

The localization policy is explicitly fail-closed: English and Japanese are both required, unsupported locales are rejected, and there is no silent cross-language fallback. Any future fallback policy would require an explicit contract change rather than happening implicitly.

Inventory records must declare `source_of_truth` and `revision`. The in-memory Sprint 3 revision guard rejects stale revisions, same-revision/different-payload conflicts, and unexpected source changes. Sprint 3 does not silently choose the production inventory system of record; activation must confirm that rule.

Category hierarchy planning validates unique keys, existing parents, acyclic relationships, and deterministic parent-before-child ordering without calling WooCommerce.

Product media planning resolves canonical media references, requires exactly one primary image when media is present, rejects ambiguous positions, and produces deterministic locale-specific manifests without uploading files.

Every product must also carry an explicit fulfillment profile. Delivery-enabled
products declare one of the approved Yamato Cool size classes and at least one
temperature mode (`frozen` or `chilled`). Pickup-only products cannot carry
delivery settings. The profile projects deterministic WooCommerce shipping
class and Phil AI OS metadata fields while preserving approval-before-payment
as a required invariant. This prevents a size-only shipping class from silently
making both frozen and chilled methods eligible for every product.

## Production transport activation model

`production_transport.py` provides the approved transport implementation without
activating it. The runtime must supply all of the following before a read request
can occur:

1. an HTTPS WooCommerce base URL;
2. a production `CredentialReference`;
3. an external secret resolver capable of resolving that opaque reference; and
4. `enabled=True`.

Mutating requests additionally require `allow_mutations=True`, a `read_write`
credential reference, and an independently GREEN activation preflight. Current
repository readiness intentionally keeps catalog/tax/legal/recovery-dependent
mutation execution blocked.

## Resilience, audit, and rollback preparation

A failure-injecting test transport and retry executor exercise transient HTTP retry policy without sleeping or using live network connectivity. The executor returns planned delays for assertions.

`MemoryAuditSink` accepts only commerce audit events whose `authority_effect` is `none`, preserving the no-implicit-production-authority boundary.

The mock rollback helper captures and restores only `MockWooCommerceTransport` state. It proves deterministic isolated rollback semantics for tests; it is not a production backup or rollback mechanism and cannot target a live WooCommerce store.

## Local development topology

`docker-compose.dev.yml` provides an isolated WordPress + MariaDB base bound to loopback only. A `local-tools` WP-CLI profile supports local installation of WooCommerce Core.

The bootstrap script is intentionally local-only:

```bash
bash commerce/woocommerce/bootstrap-local.sh
```

It starts the isolated database/WordPress services, installs WordPress locally if needed, installs/activates WooCommerce in that local environment, and refuses non-loopback targets. It does not contain or use Ruby's production domain or production WooCommerce credentials.

To inspect the local stack configuration without starting services:

```bash
docker compose --profile local-tools \
  -f commerce/woocommerce/docker-compose.dev.yml config
```

## Run isolated tests

```bash
PYTHONPATH=commerce/woocommerce/src \
  python -m unittest discover -s commerce/woocommerce/tests -v

python commerce/woocommerce/tools_validate_contracts.py
python commerce/woocommerce/tools_validate_catalog_readiness.py
```

## API compatibility baseline

The approved production transport targets the official WooCommerce REST API
`wc/v3` namespace over HTTPS. It remains disabled unless the runtime activation
conditions above are explicitly satisfied.

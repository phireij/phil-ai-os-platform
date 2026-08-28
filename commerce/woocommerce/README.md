# Sprint 3 — WooCommerce Foundation

This directory is the **bounded, inert Sprint 3 commerce foundation**.

## Approved deployment boundary

- Ruby's customer-facing WordPress + WooCommerce production site will live on Hostinger managed web hosting.
- The retained public customer domain is `https://www.rubyscakedelights.shop/`.
- Phil AI OS, Mission Control, Hermes/agents, reconciliation, audit, CX, and Operations remain on the Hostinger VPS.
- The current Hostinger Website Builder site is reference-only. Store information, contact information, and policies may be reviewed for migration after verification. Its test products and categories are explicitly excluded.

The public domain above is architecture/migration planning data only. It is **not** configured as a runtime WooCommerce API endpoint in this Sprint 3 foundation.

## Safety boundary

- No production WooCommerce consumer key/secret is stored here.
- No production WooCommerce API base URL is stored in runtime configuration.
- No live network transport is shipped in the Python adapter.
- Adapter mutations default to disabled and must be explicitly enabled only for isolated mock tests.
- Live connectivity, a production integration identity, and live commerce mutations remain CEO-gated.

## Contract and reconciliation strategy

Phil AI OS owns a bilingual canonical commerce contract. WooCommerce is treated as an integration projection, not as an implied governance authority. Bilingual canonical fields require both `en` and `ja`; locale-specific WooCommerce payloads are generated deterministically.

Japanese slugs are **explicit contract data**, not automatically transliterated. This prevents unstable slug changes across libraries or deployments.

Inventory records must declare `source_of_truth` and `revision`. The in-memory Sprint 3 revision guard rejects stale revisions, same-revision/different-payload conflicts, and unexpected source changes. Sprint 3 does not silently choose the production inventory system of record; activation must confirm that rule.

Category hierarchy planning validates unique keys, existing parents, acyclic relationships, and deterministic parent-before-child ordering without calling WooCommerce.

Product media planning resolves canonical media references, requires exactly one primary image when media is present, rejects ambiguous positions, and produces deterministic locale-specific manifests without uploading files.

## Resilience and audit preparation

A failure-injecting test transport and retry executor exercise transient HTTP retry policy without sleeping or using live network connectivity. The executor returns planned delays for assertions.

`MemoryAuditSink` accepts only commerce audit events whose `authority_effect` is `none`, preserving the Sprint 3 no-production-authority boundary.

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
```

## API compatibility baseline

The eventual activated transport targets the official WooCommerce REST API `wc/v3` namespace. The production transport itself is intentionally absent until the explicit activation gate.

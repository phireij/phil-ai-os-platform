# Sprint 3 — WooCommerce Foundation

This directory is the **bounded, inert Sprint 3 commerce foundation**.

## Safety boundary

- No production WooCommerce consumer key/secret is stored here.
- The public Ruby's customer domain may be documented as architecture/migration planning data, but no production WooCommerce API base URL is configured in runtime code.
- No live network transport is shipped in the Python adapter.
- Adapter mutations default to disabled and must be explicitly enabled only for isolated mock tests.
- Live connectivity, a production integration identity, and live commerce mutations remain CEO-gated.

## Production deployment decision

Ruby's customer-facing WordPress + WooCommerce production storefront is targeted for **Hostinger managed web hosting** using the existing public domain `https://www.rubyscakedelights.shop/`.

Phil AI OS remains on the **Hostinger VPS**. The VPS WooCommerce adapter will eventually communicate with the managed-hosting WooCommerce instance through a separately authorized API/webhook boundary.

The existing Hostinger Website Builder site is reference-only. Only store information, contact information, and policies are copy candidates, and every copied value requires verification. Existing test products and categories are explicitly excluded from migration.

See `docs/SPRINT_3_RUBYS_COMMERCE_DEPLOYMENT_DECISION_2026-08-28.md`.

## Contract strategy

Phil AI OS owns a bilingual canonical commerce contract. WooCommerce is treated as an integration projection, not as an implied governance authority. Bilingual canonical fields require both `en` and `ja`; locale-specific WooCommerce payloads are generated deterministically.

Japanese slugs are **explicit contract data**, not automatically transliterated. This prevents unstable slug changes across libraries or deployments.

Inventory records must declare `source_of_truth` and `revision`. Sprint 3 does not silently choose the production inventory system of record; activation must confirm that rule.

## Local development topology

`docker-compose.dev.yml` provides an isolated WordPress + MariaDB base on loopback only. It intentionally does not install or authenticate to a production WooCommerce store. WooCommerce Core can be installed into this local environment during the later isolated integration-test slice.

## Run isolated tests

```bash
PYTHONPATH=commerce/woocommerce/src \
  python -m unittest discover -s commerce/woocommerce/tests -v

python commerce/woocommerce/tools_validate_contracts.py
```

## API compatibility baseline

The eventual activated transport targets the official WooCommerce REST API `wc/v3` namespace. The production transport itself is intentionally absent until the explicit activation gate.

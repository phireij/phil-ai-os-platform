from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
TEMPLATE = ROOT / "fixtures" / "production-catalog-intake.template.json"
TAX_EVIDENCE = REPO_ROOT / "ops/readiness/ruby-japan-consumption-tax-status-2026-09-03.json"
CHECKOUT_EVIDENCE = REPO_ROOT / "ops/readiness/ruby-checkout-legal-payment-shipping-sync-2026-09-04.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_CATALOG_HANDOFF_FAILED: {message}")


def main() -> int:
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    tax_evidence = json.loads(TAX_EVIDENCE.read_text(encoding="utf-8"))
    checkout = json.loads(CHECKOUT_EVIDENCE.read_text(encoding="utf-8"))

    require(payload["schema_version"] == "1.0", "catalog intake schema drift")
    require(payload["environment"] == "pre-production", "catalog intake environment drift")
    require(payload["package_state"] == "draft", "template must remain draft")
    require(payload["catalog_approved"] is False, "template cannot self-approve catalog")
    require(payload["catalog_approval_ref"] is None, "template cannot invent approval reference")

    source = payload["source_contract"]
    for key in (
        "owner_source_required",
        "owner_approval_required",
        "source_updated_at_required",
        "bilingual_en_ja_required",
        "verified_media_source_required",
    ):
        require(source[key] is True, f"source contract requirement regressed: {key}")
    require(source["currency"] == "JPY", "handoff currency must remain JPY")
    require(source["intake_product_status"] == "draft", "intake products must remain draft")
    require(source["intake_product_visibility"] == "hidden", "intake products must remain hidden")
    require(source["production_write_authority_granted_by_handoff"] is False, "handoff must not grant write authority")

    requirements = payload["handoff_requirements"]
    expected_markers = (
        "owner-approved product list",
        "category hierarchy",
        "English and Japanese",
        "JPY",
        "fulfillment",
        "primary image",
        "source provenance",
        "approval reference",
    )
    joined = "\n".join(requirements)
    for marker in expected_markers:
        require(marker in joined, f"handoff requirement missing: {marker}")

    tax = payload["tax_decision"]
    require(tax["taxable_business_status"] == "exempt", "2026 tax posture drift")
    require(tax["qualified_invoice_status"] == "not_registered", "Qualified Invoice posture drift")
    require(tax["qualified_invoice_registration_number"] is None, "unexpected Qualified Invoice number")
    require(tax["yamato_shipping_separately_charged"] == "yes", "verified Yamato shipping treatment not reconciled")
    require(tax["cod_fee_treatment"] == "not_offered", "COD treatment must match disabled checkout state")
    require(tax["implementation_route"] == "tax_disabled_candidate", "tax-disabled implementation route drift")
    require(tax["decision_evidence_ref"] == "ops/readiness/ruby-japan-consumption-tax-status-2026-09-03.json", "tax evidence ref drift")

    require(tax_evidence["decision"]["consumption_tax_status"] == "exempt", "tax evidence no longer supports exempt status")
    require(tax_evidence["decision"]["qualified_invoice_status"] == "not_registered", "tax evidence invoice posture drift")
    require(tax_evidence["decision"]["tax_decision_ready"] is True, "tax decision evidence is no longer GREEN")
    require(checkout["verified_prerequisites"]["production_shipping_configuration_verified"] is True, "shipping configuration evidence not GREEN")
    require(checkout["verified_prerequisites"]["production_shipping_rates_verified"] is True, "shipping rate evidence not GREEN")
    require("cod" in checkout["woocommerce_checkout_verification"]["disabled_gateway_ids"], "COD is no longer disabled in verified checkout snapshot")

    refs = payload["readiness_evidence_refs"]
    require("ops/readiness/ruby-japan-consumption-tax-status-2026-09-03.json" in refs, "tax readiness evidence ref missing")
    require("ops/readiness/ruby-checkout-legal-payment-shipping-sync-2026-09-04.json" in refs, "checkout readiness evidence ref missing")

    require(payload["categories"] == [] and payload["media"] == [] and payload["products"] == [], "template must not fabricate owner catalog data")
    require(payload["mutation_authorized"] is False, "catalog handoff must not authorize mutation")
    require(payload["production_publish_authorized"] is False, "catalog handoff must not authorize publication")

    print(
        "PHIL_AI_OS_CATALOG_HANDOFF_TEMPLATE_GREEN "
        "owner_input_pending=true tax=exempt shipping=reconciled cod=not_offered "
        "mutation_authorized=false production_publish_authorized=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

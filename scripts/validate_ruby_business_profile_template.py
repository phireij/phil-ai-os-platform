#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/commerce/verified-ruby-business-profile.schema.json"
TEMPLATE = ROOT / "ops/readiness/verified-ruby-business-profile.template.json"
FORM = ROOT / "docs/RUBY_BUSINESS_PROFILE_VERIFICATION_FORM_2026-08-28.md"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_RUBY_BUSINESS_PROFILE_VALIDATION_FAILED: {message}")


def main() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    props = schema["properties"]
    if props["public_domain"].get("const") != "https://www.rubyscakedelights.shop/":
        fail("public domain drift")
    if props["source_site_role"].get("const") != "reference-only":
        fail("source site must remain reference-only")
    if props["excluded_migration_sections"].get("const") != ["products", "categories"]:
        fail("product/category migration exclusion drift")
    if props["profile_complete"].get("type") != "boolean":
        fail("profile_complete must be a boolean state, not permanently locked")
    if props["production_publish_authorized"].get("const") is not False:
        fail("business-profile verification must not grant publication authority")

    if template.get("profile_id") != "ruby-business-profile-v1":
        fail("profile id drift")
    if template.get("public_domain") != "https://www.rubyscakedelights.shop/":
        fail("template public domain drift")
    if template.get("source_site_role") != "reference-only":
        fail("template source role drift")
    if template.get("excluded_migration_sections") != ["products", "categories"]:
        fail("template migration exclusions drift")
    if template.get("profile_complete") is not False:
        fail("unverified template must remain incomplete")
    if template.get("production_publish_authorized") is not False:
        fail("template must not authorize production publication")

    required_sections = {
        "store_information": {"business_name", "business_description", "address", "operating_hours", "pickup_instructions"},
        "contact_information": {"phone", "email", "instagram", "facebook", "other_contact"},
        "policies": {"privacy_policy", "terms_conditions", "cancellation_refund_policy", "pickup_order_policy", "allergen_disclaimer"},
    }
    field_count = 0
    for section, fields in required_sections.items():
        actual = template.get(section)
        if not isinstance(actual, dict) or set(actual) != fields:
            fail(f"{section} field set drift")
        for field, record in actual.items():
            field_count += 1
            if field == "phone":
                if record.get("verification_status") != "replace_required":
                    fail("phone must remain replace_required until CEO verification")
                if record.get("value") is not None:
                    fail("unverified phone value must not be populated")
            else:
                if record.get("verification_status") != "unverified":
                    fail(f"unverified template field must remain unverified: {section}.{field}")
            if record.get("verified_at") is not None or record.get("verified_by") is not None:
                fail(f"template must not contain fake verification metadata: {section}.{field}")
            if record.get("value") is not None:
                fail(f"template must not invent business data: {section}.{field}")

    form_text = FORM.read_text(encoding="utf-8")
    required_form_phrases = (
        "AWAITING CEO / BUSINESS VERIFICATION",
        "Existing test products — **DO NOT MIGRATE**",
        "Existing test categories — **DO NOT MIGRATE**",
        "Phone — REQUIRED UPDATE/VERIFICATION",
        "production_publish_authorized` remains **false**",
        "PHIL_AI_OS_RUBY_BUSINESS_PROFILE_FORM_AWAITING_VERIFICATION",
    )
    for phrase in required_form_phrases:
        if phrase not in form_text:
            fail(f"verification form missing safeguard: {phrase}")

    print(
        "PHIL_AI_OS_RUBY_BUSINESS_PROFILE_TEMPLATE_GREEN "
        f"fields={field_count} profile_complete=false publish_authorized=false"
    )
    print(
        "PHIL_AI_OS_RUBY_BUSINESS_PROFILE_MIGRATION_BOUNDARY_GREEN "
        "copy=store_contact_policies exclude=products_categories phone=replace_required"
    )


if __name__ == "__main__":
    main()

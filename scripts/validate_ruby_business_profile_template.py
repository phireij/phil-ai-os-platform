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
        fail("profile_complete must remain a boolean completion state")
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
    if template.get("production_publish_authorized") is not False:
        fail("template must not authorize production publication")

    required_sections = {
        "store_information": {"business_name", "business_description", "address", "operating_hours", "pickup_instructions"},
        "contact_information": {"phone", "email", "instagram", "facebook", "other_contact"},
        "policies": {"privacy_policy", "terms_conditions", "cancellation_refund_policy", "pickup_order_policy", "allergen_disclaimer"},
    }

    field_count = 0
    resolved_count = 0
    verified_count = 0
    for section, fields in required_sections.items():
        actual = template.get(section)
        if not isinstance(actual, dict) or set(actual) != fields:
            fail(f"{section} field set drift")

        for field, record in actual.items():
            field_count += 1
            status = record.get("verification_status")
            value = record.get("value")
            source = record.get("source")
            verified_at = record.get("verified_at")
            verified_by = record.get("verified_by")
            notes = record.get("notes")

            if status == "unverified":
                if value is not None or verified_at is not None or verified_by is not None:
                    fail(f"unverified field contains asserted data or verification metadata: {section}.{field}")
            elif status == "replace_required":
                if verified_at is not None or verified_by is not None:
                    fail(f"replace_required field must not carry verification metadata: {section}.{field}")
            elif status == "verified":
                if not isinstance(value, str) or not value.strip():
                    fail(f"verified field requires a non-empty value: {section}.{field}")
                if source == "not_provided":
                    fail(f"verified field requires a real source: {section}.{field}")
                if not verified_at or not verified_by:
                    fail(f"verified field requires verification metadata: {section}.{field}")
                verified_count += 1
                resolved_count += 1
            elif status == "not_applicable":
                if not verified_at or not verified_by or not notes:
                    fail(f"not_applicable field requires explicit verification metadata and reason: {section}.{field}")
                resolved_count += 1
            else:
                fail(f"unsupported verification status: {section}.{field}={status!r}")

    phone = template["contact_information"]["phone"]
    if phone.get("value") != "050-1785-0575":
        fail("verified business phone drift")
    if phone.get("source") != "user_confirmed":
        fail("business phone must remain user-confirmed unless re-verified through another approved source")
    if phone.get("verification_status") != "verified":
        fail("business phone must remain verified")
    if not phone.get("verified_at") or not phone.get("verified_by"):
        fail("business phone verification metadata missing")

    expected_complete = resolved_count == field_count
    if template.get("profile_complete") is not expected_complete:
        fail(
            "profile_complete must be true iff every required field is verified or explicitly not_applicable "
            f"(resolved={resolved_count}/{field_count})"
        )

    form_text = FORM.read_text(encoding="utf-8")
    required_form_phrases = (
        "PARTIAL BUSINESS VERIFICATION — PHONE CONFIRMED",
        "Existing test products — **DO NOT MIGRATE**",
        "Existing test categories — **DO NOT MIGRATE**",
        "Phone — VERIFIED",
        "050-1785-0575",
        "production_publish_authorized` remains **false**",
        "PHIL_AI_OS_RUBY_BUSINESS_PROFILE_PARTIAL_VERIFICATION",
    )
    for phrase in required_form_phrases:
        if phrase not in form_text:
            fail(f"verification form missing safeguard: {phrase}")

    print(
        "PHIL_AI_OS_RUBY_BUSINESS_PROFILE_TEMPLATE_GREEN "
        f"fields={field_count} verified={verified_count} resolved={resolved_count} "
        f"profile_complete={str(expected_complete).lower()} publish_authorized=false"
    )
    print(
        "PHIL_AI_OS_RUBY_BUSINESS_PROFILE_PHONE_VERIFIED_GREEN "
        "phone=050-1785-0575 source=user_confirmed"
    )
    print(
        "PHIL_AI_OS_RUBY_BUSINESS_PROFILE_MIGRATION_BOUNDARY_GREEN "
        "copy=store_contact_policies exclude=products_categories"
    )


if __name__ == "__main__":
    main()

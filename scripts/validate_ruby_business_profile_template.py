#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/commerce/verified-ruby-business-profile.schema.json"
TEMPLATE = ROOT / "ops/readiness/verified-ruby-business-profile.template.json"
FORM = ROOT / "docs/RUBY_BUSINESS_PROFILE_VERIFICATION_FORM_2026-08-28.md"
DRAFTS = ROOT / "docs/RUBY_BUSINESS_PROFILE_CUSTOMER_CONTENT_DRAFTS_2026-08-28.md"


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
    not_applicable_count = 0
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
                if source == "not_provided" or not verified_at or not verified_by or not notes:
                    fail(f"not_applicable field requires explicit source, verification metadata and reason: {section}.{field}")
                not_applicable_count += 1
                resolved_count += 1
            else:
                fail(f"unsupported verification status: {section}.{field}={status!r}")

    expected_verified = {
        ("store_information", "business_name"): "Ruby's Cake Delights",
        ("store_information", "address"): "〒272-0034 千葉県市川市市川1-26-15花亀ビル1F-B (Chiba-ken, Ichikawa-shi, Ichikawa 1-26-15 Hanakame Bldg. 1F-B)",
        ("store_information", "operating_hours"): "Wednesday to Saturday: 14:00-20:00. Pickup hours are the same as operating hours.",
        ("contact_information", "phone"): "050-1785-0575",
        ("contact_information", "email"): "Primary: info@rubyscakedelights.shop; Alias: order@rubyscakedelights.shop",
        ("contact_information", "instagram"): "@rubyscakedelights",
        ("contact_information", "facebook"): "https://www.facebook.com/RubysCakeDelights",
    }
    for (section, field), expected_value in expected_verified.items():
        record = template[section][field]
        if record.get("value") != expected_value:
            fail(f"verified value drift: {section}.{field}")
        if record.get("source") != "user_confirmed" or record.get("verification_status") != "verified":
            fail(f"verified source/status drift: {section}.{field}")
        if not record.get("verified_at") or not record.get("verified_by"):
            fail(f"verified metadata missing: {section}.{field}")

    for section, field in (
        ("store_information", "pickup_instructions"),
        ("contact_information", "other_contact"),
    ):
        record = template[section][field]
        if record.get("verification_status") != "not_applicable" or record.get("source") != "user_confirmed":
            fail(f"not-applicable business decision drift: {section}.{field}")

    if "mid-September 2026" not in template["store_information"]["operating_hours"].get("notes", ""):
        fail("operating hours must retain mid-September 2026 re-verification note")

    for field in ("business_description",):
        record = template["store_information"][field]
        if record.get("verification_status") != "unverified" or record.get("value") is not None:
            fail(f"draft field must remain unverified until approval: store_information.{field}")

    for field in ("cancellation_refund_policy", "pickup_order_policy", "allergen_disclaimer"):
        record = template["policies"][field]
        if record.get("verification_status") != "unverified" or record.get("value") is not None:
            fail(f"policy draft must remain unverified until approval: policies.{field}")
        if "RUBY_BUSINESS_PROFILE_CUSTOMER_CONTENT_DRAFTS_2026-08-28.md" not in record.get("notes", ""):
            fail(f"policy draft evidence reference missing: policies.{field}")

    for field in ("privacy_policy", "terms_conditions"):
        record = template["policies"][field]
        if record.get("verification_status") != "unverified" or record.get("value") is not None:
            fail(f"undrafted policy must remain unverified: policies.{field}")

    if (verified_count, not_applicable_count, resolved_count, field_count) != (7, 2, 9, 15):
        fail(
            "verification progress drift "
            f"verified={verified_count} not_applicable={not_applicable_count} resolved={resolved_count} fields={field_count}"
        )

    expected_complete = resolved_count == field_count
    if template.get("profile_complete") is not expected_complete:
        fail(
            "profile_complete must be true iff every required field is verified or explicitly not_applicable "
            f"(resolved={resolved_count}/{field_count})"
        )

    form_text = FORM.read_text(encoding="utf-8")
    required_form_phrases = (
        "PARTIAL BUSINESS VERIFICATION — CORE DETAILS CONFIRMED / DRAFT POLICIES PENDING",
        "Ruby's Cake Delights",
        "050-1785-0575",
        "info@rubyscakedelights.shop",
        "order@rubyscakedelights.shop",
        "@rubyscakedelights",
        "https://www.facebook.com/RubysCakeDelights",
        "Resolved: **9 / 15**",
        "mid-September 2026",
        "Existing test products — **DO NOT MIGRATE**",
        "Existing test categories — **DO NOT MIGRATE**",
        "production_publish_authorized` remains **false**",
        "PHIL_AI_OS_RUBY_BUSINESS_PROFILE_CORE_DETAILS_VERIFIED_DRAFTS_PENDING",
    )
    for phrase in required_form_phrases:
        if phrase not in form_text:
            fail(f"verification form missing safeguard/detail: {phrase}")

    draft_text = DRAFTS.read_text(encoding="utf-8")
    required_draft_phrases = (
        "DRAFT — AWAITING CEO / BUSINESS OWNER APPROVAL",
        "## 1. Business Description — Draft",
        "## 2. Cancellation & Refund Policy — Draft",
        "## 3. Pickup & Order Policy — Draft",
        "## 4. Allergen Information & Disclaimer — Draft",
        "48 hours or more",
        "50% of the order total",
        "100% of the order total",
        "cross-contact with allergens may occur",
        "PHIL_AI_OS_RUBY_CUSTOMER_CONTENT_DRAFTS_AWAITING_APPROVAL",
    )
    for phrase in required_draft_phrases:
        if phrase not in draft_text:
            fail(f"customer-content draft missing safeguard/content: {phrase}")

    print(
        "PHIL_AI_OS_RUBY_BUSINESS_PROFILE_TEMPLATE_GREEN "
        f"fields={field_count} verified={verified_count} not_applicable={not_applicable_count} "
        f"resolved={resolved_count} profile_complete={str(expected_complete).lower()} publish_authorized=false"
    )
    print("PHIL_AI_OS_RUBY_BUSINESS_PROFILE_CORE_DETAILS_GREEN resolved=9/15 hours_recheck=mid_september_2026")
    print("PHIL_AI_OS_RUBY_BUSINESS_PROFILE_DRAFT_BOUNDARY_GREEN drafts=4 approved=false")
    print("PHIL_AI_OS_RUBY_BUSINESS_PROFILE_MIGRATION_BOUNDARY_GREEN copy=store_contact_policies exclude=products_categories")


if __name__ == "__main__":
    main()

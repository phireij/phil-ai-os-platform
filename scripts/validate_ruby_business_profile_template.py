#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/commerce/verified-ruby-business-profile.schema.json"
TEMPLATE = ROOT / "ops/readiness/verified-ruby-business-profile.template.json"
FORM = ROOT / "docs/RUBY_BUSINESS_PROFILE_VERIFICATION_FORM_2026-08-28.md"
DRAFTS = ROOT / "docs/RUBY_BUSINESS_PROFILE_CUSTOMER_CONTENT_DRAFTS_2026-08-28.md"
POLICY_DRAFTS = ROOT / "docs/RUBY_PRIVACY_POLICY_TERMS_DRAFTS_2026-08-29.md"

APPROVED_DESCRIPTION = (
    "Ruby's Cake Delights is a neighborhood food and dessert shop in Ichikawa, Chiba, offering "
    "handcrafted cakes, pastries, desserts, and satisfying savory meals for everyday enjoyment and "
    "special occasions. Alongside our sweets, our growing food menu includes favorites such as "
    "Spaghetti, Palabok, Baked Macaroni, and Fried Chicken in a variety of flavors. We prepare our "
    "products with care and welcome customers for convenient pickup at our Ichikawa shop."
)


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
        fail("profile_complete must remain boolean")
    if props["production_publish_authorized"].get("const") is not False:
        fail("verification must not grant publication authority")

    if template.get("profile_id") != "ruby-business-profile-v1":
        fail("profile id drift")
    if template.get("public_domain") != "https://www.rubyscakedelights.shop/":
        fail("template domain drift")
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

    field_count = verified_count = not_applicable_count = resolved_count = 0
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
                    fail(f"unverified field contains asserted verification data: {section}.{field}")
            elif status == "replace_required":
                if verified_at is not None or verified_by is not None:
                    fail(f"replace_required field carries verification metadata: {section}.{field}")
            elif status == "verified":
                if not isinstance(value, str) or not value.strip():
                    fail(f"verified field requires non-empty value: {section}.{field}")
                if source == "not_provided" or not verified_at or not verified_by:
                    fail(f"verified field missing real source/metadata: {section}.{field}")
                verified_count += 1
                resolved_count += 1
            elif status == "not_applicable":
                if source == "not_provided" or not verified_at or not verified_by or not notes:
                    fail(f"not_applicable field missing source/metadata/reason: {section}.{field}")
                not_applicable_count += 1
                resolved_count += 1
            else:
                fail(f"unsupported status: {section}.{field}={status!r}")

    expected_verified_values = {
        ("store_information", "business_name"): "Ruby's Cake Delights",
        ("store_information", "business_description"): APPROVED_DESCRIPTION,
        ("store_information", "address"): "〒272-0034 千葉県市川市市川1-26-15花亀ビル1F-B (Chiba-ken, Ichikawa-shi, Ichikawa 1-26-15 Hanakame Bldg. 1F-B)",
        ("store_information", "operating_hours"): "Wednesday to Saturday: 14:00-20:00. Pickup hours are the same as operating hours.",
        ("contact_information", "phone"): "050-1785-0575",
        ("contact_information", "email"): "Primary: info@rubyscakedelights.shop; Alias: order@rubyscakedelights.shop",
        ("contact_information", "instagram"): "@rubyscakedelights",
        ("contact_information", "facebook"): "https://www.facebook.com/RubysCakeDelights",
    }
    for (section, field), expected in expected_verified_values.items():
        record = template[section][field]
        if record.get("value") != expected or record.get("source") != "user_confirmed" or record.get("verification_status") != "verified":
            fail(f"verified value/source/status drift: {section}.{field}")
        if not record.get("verified_at") or not record.get("verified_by"):
            fail(f"verified metadata missing: {section}.{field}")

    for section, field in (("store_information", "pickup_instructions"), ("contact_information", "other_contact")):
        record = template[section][field]
        if record.get("verification_status") != "not_applicable" or record.get("source") != "user_confirmed":
            fail(f"not-applicable decision drift: {section}.{field}")

    if "mid-September 2026" not in template["store_information"]["operating_hours"].get("notes", ""):
        fail("hours re-verification note missing")

    description = template["store_information"]["business_description"]
    desc_notes = description.get("notes", "")
    for phrase in ("approved", "September 13, 2026", "not WooCommerce catalog authority"):
        if phrase.lower() not in desc_notes.lower():
            fail(f"approved business description note missing: {phrase}")

    approved_policies = {
        "cancellation_refund_policy": "section 2",
        "pickup_order_policy": "section 3",
        "allergen_disclaimer": "section 4",
    }
    for field, section_ref in approved_policies.items():
        record = template["policies"][field]
        if record.get("verification_status") != "verified" or record.get("source") != "user_confirmed":
            fail(f"approved policy status/source drift: policies.{field}")
        if "RUBY_BUSINESS_PROFILE_CUSTOMER_CONTENT_DRAFTS_2026-08-28.md" not in record.get("value", ""):
            fail(f"approved policy canonical document reference missing: policies.{field}")
        if section_ref not in record.get("value", ""):
            fail(f"approved policy section reference missing: policies.{field}")

    for field in ("privacy_policy", "terms_conditions"):
        record = template["policies"][field]
        if record.get("verification_status") != "unverified" or record.get("value") is not None:
            fail(f"drafted policy must remain unverified until approval: policies.{field}")
        if record.get("source") != "draft_prepared_pending_approval":
            fail(f"drafted policy source drift: policies.{field}")
        notes = record.get("notes", "")
        if "RUBY_PRIVACY_POLICY_TERMS_DRAFTS_2026-08-29.md" not in notes or "approval" not in notes.lower():
            fail(f"drafted policy approval boundary missing: policies.{field}")

    if (verified_count, not_applicable_count, resolved_count, field_count) != (11, 2, 13, 15):
        fail(f"verification progress drift verified={verified_count} n/a={not_applicable_count} resolved={resolved_count} fields={field_count}")

    expected_complete = resolved_count == field_count
    if template.get("profile_complete") is not expected_complete:
        fail(f"profile_complete drift resolved={resolved_count}/{field_count}")

    form_text = FORM.read_text(encoding="utf-8")
    for phrase in (
        "13/15 RESOLVED / PRIVACY + TERMS DRAFTED PENDING APPROVAL",
        "Business description — VERIFIED / APPROVED",
        "Privacy policy — DRAFTED / PENDING APPROVAL",
        "Terms & conditions — DRAFTED / PENDING APPROVAL",
        "Resolved: **13 / 15**",
        "Verified: **11**",
        "特定商取引法に基づく表記",
        "Existing test products — **DO NOT MIGRATE**",
        "Existing test categories — **DO NOT MIGRATE**",
        "production_publish_authorized` remains **false**",
        "PHIL_AI_OS_RUBY_BUSINESS_PROFILE_13_OF_15_RESOLVED_PRIVACY_TERMS_DRAFTED_PENDING_APPROVAL",
    ):
        if phrase not in form_text:
            fail(f"verification form missing detail/safeguard: {phrase}")

    draft_text = DRAFTS.read_text(encoding="utf-8")
    for phrase in (
        "BUSINESS DESCRIPTION + 3 POLICIES APPROVED",
        "## 1. Business Description — APPROVED",
        APPROVED_DESCRIPTION,
        "September 13, 2026",
        "## 2. Cancellation & Refund Policy — APPROVED",
        "## 3. Pickup & Order Policy — APPROVED",
        "## 4. Allergen Information & Disclaimer — APPROVED WORDING",
        "PHIL_AI_OS_RUBY_CUSTOMER_CONTENT_DESCRIPTION_AND_3_POLICIES_APPROVED",
    ):
        if phrase not in draft_text:
            fail(f"customer-content record missing content/safeguard: {phrase}")

    policy_text = POLICY_DRAFTS.read_text(encoding="utf-8")
    for phrase in (
        "DRAFT — CEO / BUSINESS-OWNER APPROVAL REQUIRED",
        "# 1. Privacy Policy — Draft",
        "Act on the Protection of Personal Information (APPI)",
        "KOMOJU",
        "does not intend to store complete payment-card numbers or card security codes",
        "non-essential advertising, behavioral tracking or analytics",
        "# 2. Terms & Conditions — Draft",
        "Nothing in these Terms is intended to exclude or restrict customer rights",
        "48 hours or more before scheduled pickup",
        "cross-contact may occur",
        "特定商取引法に基づく表記",
        "production_publish_authorized` must remain false",
        "PHIL_AI_OS_RUBY_PRIVACY_TERMS_DRAFTS_PENDING_APPROVAL",
    ):
        if phrase not in policy_text:
            fail(f"privacy/terms draft missing content/safeguard: {phrase}")

    print(
        "PHIL_AI_OS_RUBY_BUSINESS_PROFILE_TEMPLATE_GREEN "
        f"fields={field_count} verified={verified_count} not_applicable={not_applicable_count} "
        f"resolved={resolved_count} profile_complete={str(expected_complete).lower()} publish_authorized=false"
    )
    print("PHIL_AI_OS_RUBY_BUSINESS_PROFILE_PROGRESS_GREEN resolved=13/15 pending=privacy_terms_approval")
    print("PHIL_AI_OS_RUBY_PRIVACY_TERMS_DRAFT_BOUNDARY_GREEN approved=false profile_complete=false publish_authorized=false")
    print("PHIL_AI_OS_RUBY_BUSINESS_DESCRIPTION_APPROVAL_GREEN bilingual=true")
    print("PHIL_AI_OS_RUBY_POLICY_APPROVAL_GREEN approved=cancellation_refund,pickup_order,allergen")
    print("PHIL_AI_OS_RUBY_MEAL_ROLLOUT_NOTE_GREEN launch_date=2026-09-13 catalog_authority=false")
    print("PHIL_AI_OS_RUBY_BUSINESS_PROFILE_MIGRATION_BOUNDARY_GREEN copy=store_contact_policies exclude=products_categories")


if __name__ == "__main__":
    main()

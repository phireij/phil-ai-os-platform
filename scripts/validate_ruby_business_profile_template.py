#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/commerce/verified-ruby-business-profile.schema.json"
TEMPLATE = ROOT / "ops/readiness/verified-ruby-business-profile.template.json"
FORM = ROOT / "docs/RUBY_BUSINESS_PROFILE_VERIFICATION_FORM_2026-08-28.md"
CUSTOMER_CONTENT = ROOT / "docs/RUBY_BUSINESS_PROFILE_CUSTOMER_CONTENT_DRAFTS_2026-08-28.md"
POLICY_TEXT = ROOT / "docs/RUBY_PRIVACY_POLICY_TERMS_DRAFTS_2026-08-29.md"
POLICY_APPROVAL = ROOT / "docs/RUBY_PRIVACY_TERMS_APPROVAL_RECORD_2026-08-29.md"
TOKUSHOHO = ROOT / "docs/RUBY_TOKUSHOHO_EXPANSION_DRAFT_2026-08-29.md"

APPROVED_DESCRIPTION = (
    "Ruby's Cake Delights is a neighborhood food and dessert shop in Ichikawa, Chiba, offering "
    "handcrafted cakes, pastries, desserts, and satisfying savory meals for everyday enjoyment and "
    "special occasions. Alongside our sweets, our growing food menu includes favorites such as "
    "Spaghetti, Palabok, Baked Macaroni, and Fried Chicken in a variety of flavors. We prepare our "
    "products with care and welcome customers for convenient pickup at our Ichikawa shop."
)


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_RUBY_BUSINESS_PROFILE_VALIDATION_FAILED: {message}")


def require(text: str, phrases: tuple[str, ...], label: str) -> None:
    for phrase in phrases:
        if phrase not in text:
            fail(f"{label} missing: {phrase}")


def main() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    profile = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    props = schema["properties"]
    if props["public_domain"].get("const") != "https://www.rubyscakedelights.shop/":
        fail("public domain drift")
    if props["source_site_role"].get("const") != "reference-only":
        fail("source site role drift")
    if props["excluded_migration_sections"].get("const") != ["products", "categories"]:
        fail("migration exclusion drift")
    if props["profile_complete"].get("type") != "boolean":
        fail("profile_complete schema must remain boolean")
    if props["production_publish_authorized"].get("const") is not False:
        fail("schema must keep production publication unauthorized")

    if profile.get("profile_id") != "ruby-business-profile-v1":
        fail("profile id drift")
    if profile.get("public_domain") != "https://www.rubyscakedelights.shop/":
        fail("profile domain drift")
    if profile.get("source_site_role") != "reference-only":
        fail("profile source-site role drift")
    if profile.get("excluded_migration_sections") != ["products", "categories"]:
        fail("profile migration exclusion drift")
    if profile.get("production_publish_authorized") is not False:
        fail("profile must not authorize production publication")

    expected_fields = {
        "store_information": {"business_name", "business_description", "address", "operating_hours", "pickup_instructions"},
        "contact_information": {"phone", "email", "instagram", "facebook", "other_contact"},
        "policies": {"privacy_policy", "terms_conditions", "cancellation_refund_policy", "pickup_order_policy", "allergen_disclaimer"},
    }

    verified = not_applicable = resolved = total = 0
    for section, fields in expected_fields.items():
        records = profile.get(section)
        if not isinstance(records, dict) or set(records) != fields:
            fail(f"field set drift: {section}")
        for field, record in records.items():
            total += 1
            status = record.get("verification_status")
            if status == "verified":
                if record.get("source") != "user_confirmed":
                    fail(f"verified source must be user_confirmed: {section}.{field}")
                if not isinstance(record.get("value"), str) or not record["value"].strip():
                    fail(f"verified field missing value: {section}.{field}")
                if not record.get("verified_at") or not record.get("verified_by"):
                    fail(f"verified field missing metadata: {section}.{field}")
                verified += 1
                resolved += 1
            elif status == "not_applicable":
                if record.get("source") != "user_confirmed" or not record.get("verified_at") or not record.get("verified_by") or not record.get("notes"):
                    fail(f"not-applicable decision incomplete: {section}.{field}")
                not_applicable += 1
                resolved += 1
            else:
                fail(f"all 15 profile fields must now be resolved: {section}.{field}={status!r}")

    if (verified, not_applicable, resolved, total) != (13, 2, 15, 15):
        fail(f"profile count drift verified={verified} n/a={not_applicable} resolved={resolved} total={total}")
    if profile.get("profile_complete") is not True:
        fail("15/15 resolved requires profile_complete=true")

    expected_values = {
        ("store_information", "business_name"): "Ruby's Cake Delights",
        ("store_information", "business_description"): APPROVED_DESCRIPTION,
        ("store_information", "address"): "〒272-0034 千葉県市川市市川1-26-15花亀ビル1F-B (Chiba-ken, Ichikawa-shi, Ichikawa 1-26-15 Hanakame Bldg. 1F-B)",
        ("store_information", "operating_hours"): "Wednesday to Saturday: 14:00-20:00. Pickup hours are the same as operating hours.",
        ("contact_information", "phone"): "050-1785-0575",
        ("contact_information", "email"): "Primary: info@rubyscakedelights.shop; Alias: order@rubyscakedelights.shop",
        ("contact_information", "instagram"): "@rubyscakedelights",
        ("contact_information", "facebook"): "https://www.facebook.com/RubysCakeDelights",
    }
    for (section, field), value in expected_values.items():
        if profile[section][field].get("value") != value:
            fail(f"verified value drift: {section}.{field}")

    for section, field in (("store_information", "pickup_instructions"), ("contact_information", "other_contact")):
        if profile[section][field].get("verification_status") != "not_applicable":
            fail(f"N/A decision drift: {section}.{field}")

    if "mid-September 2026" not in profile["store_information"]["operating_hours"].get("notes", ""):
        fail("operating-hours recheck safeguard missing")

    privacy = profile["policies"]["privacy_policy"]
    terms = profile["policies"]["terms_conditions"]
    for field, record, section_ref in (
        ("privacy_policy", privacy, "section 1"),
        ("terms_conditions", terms, "section 2"),
    ):
        if record.get("verification_status") != "verified" or record.get("source") != "user_confirmed":
            fail(f"privacy/terms approval state drift: {field}")
        value = record.get("value", "")
        if "RUBY_PRIVACY_POLICY_TERMS_DRAFTS_2026-08-29.md" not in value or section_ref not in value:
            fail(f"privacy/terms canonical source reference missing: {field}")
        if "RUBY_PRIVACY_TERMS_APPROVAL_RECORD_2026-08-29.md" not in value:
            fail(f"privacy/terms approval record missing: {field}")
        if record.get("verified_at") != "2026-08-29T03:38:00+09:00":
            fail(f"privacy/terms approval timestamp drift: {field}")

    form_text = FORM.read_text(encoding="utf-8")
    require(form_text, (
        "PROFILE CONTENT COMPLETE — 15/15 RESOLVED / PRODUCTION PUBLICATION STILL GATED",
        "Privacy Policy — VERIFIED / APPROVED",
        "Terms & Conditions — VERIFIED / APPROVED",
        "Verified: **13**",
        "Resolved: **15 / 15**",
        "profile_complete: true",
        "production_publish_authorized` remains **false**",
        "特定商取引法に基づく表記",
        "Existing test products — **DO NOT MIGRATE**",
        "Existing test categories — **DO NOT MIGRATE**",
        "PHIL_AI_OS_RUBY_BUSINESS_PROFILE_15_OF_15_RESOLVED_PROFILE_COMPLETE_PUBLISH_GATED",
    ), "verification form")

    approval_text = POLICY_APPROVAL.read_text(encoding="utf-8")
    require(approval_text, (
        "Section 1 — Privacy Policy: APPROVED / VERIFIED",
        "Section 2 — Terms & Conditions: APPROVED / VERIFIED",
        "Resolved: **15 / 15**",
        "`profile_complete`: **true**",
        "`production_publish_authorized`: **false**",
        "PHIL_AI_OS_RUBY_PRIVACY_TERMS_APPROVED_PROFILE_15_OF_15_PUBLISH_GATED",
    ), "privacy/terms approval record")

    policy_text = POLICY_TEXT.read_text(encoding="utf-8")
    require(policy_text, (
        "Act on the Protection of Personal Information (APPI)",
        "KOMOJU",
        "non-essential advertising, behavioral tracking or analytics",
        "Nothing in these Terms is intended to exclude or restrict customer rights",
        "48 hours or more before scheduled pickup",
        "cross-contact may occur",
        "特定商取引法に基づく表記",
    ), "approved privacy/terms source text")

    customer_text = CUSTOMER_CONTENT.read_text(encoding="utf-8")
    require(customer_text, (
        "BUSINESS DESCRIPTION + 3 POLICIES APPROVED",
        "September 13, 2026",
        "PHIL_AI_OS_RUBY_CUSTOMER_CONTENT_DESCRIPTION_AND_3_POLICIES_APPROVED",
    ), "customer content")

    tokushoho = TOKUSHOHO.read_text(encoding="utf-8")
    require(tokushoho, (
        "WORKING DRAFT — EXISTING LIVE PAGE RECONCILIATION REQUIRED BEFORE APPROVAL/PUBLICATION",
        "existing_live_page_retrieved: false",
        "販売業者",
        "PENDING — recover exact current-page value",
        "050-1785-0575",
        "48 hours or more before scheduled pickup",
        "profile_complete`: **true**",
        "production_publish_authorized`: **false**",
        "PHIL_AI_OS_RUBY_TOKUSHOHO_EXPANSION_DRAFT_SOURCE_RECONCILIATION_PENDING",
    ), "Tokushoho expansion draft")

    print("PHIL_AI_OS_RUBY_BUSINESS_PROFILE_TEMPLATE_GREEN fields=15 verified=13 not_applicable=2 resolved=15 profile_complete=true publish_authorized=false")
    print("PHIL_AI_OS_RUBY_BUSINESS_PROFILE_15_OF_15_GREEN unresolved=0")
    print("PHIL_AI_OS_RUBY_PRIVACY_TERMS_APPROVAL_GREEN verified=true publish_authorized=false")
    print("PHIL_AI_OS_RUBY_TOKUSHOHO_SOURCE_BOUNDARY_GREEN existing_page_retrieved=false publication_authorized=false")
    print("PHIL_AI_OS_RUBY_BUSINESS_PROFILE_MIGRATION_BOUNDARY_GREEN copy=store_contact_policies exclude=products_categories")


if __name__ == "__main__":
    main()

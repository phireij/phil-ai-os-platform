#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/commerce/verified-ruby-business-profile.schema.json"
PROFILE = ROOT / "ops/readiness/verified-ruby-business-profile.template.json"
FORM = ROOT / "docs/RUBY_BUSINESS_PROFILE_VERIFICATION_FORM_2026-08-28.md"
CUSTOMER_CONTENT = ROOT / "docs/RUBY_BUSINESS_PROFILE_CUSTOMER_CONTENT_DRAFTS_2026-08-28.md"
POLICY_TEXT = ROOT / "docs/RUBY_PRIVACY_POLICY_TERMS_DRAFTS_2026-08-29.md"
POLICY_APPROVAL = ROOT / "docs/RUBY_PRIVACY_TERMS_APPROVAL_RECORD_2026-08-29.md"
TOKUSHOHO = ROOT / "docs/RUBY_TOKUSHOHO_EXPANSION_DRAFT_2026-08-29.md"
TOKUSHOHO_SOURCE = ROOT / "docs/RUBY_TOKUSHOHO_LEGACY_SOURCE_CAPTURE_2026-08-29.md"

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
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    props = schema["properties"]
    if props["public_domain"].get("const") != "https://www.rubyscakedelights.shop/":
        fail("public domain drift")
    if props["source_site_role"].get("const") != "reference-only":
        fail("source site role drift")
    if props["excluded_migration_sections"].get("const") != ["products", "categories"]:
        fail("migration exclusion drift")
    if props["profile_complete"].get("type") != "boolean":
        fail("profile_complete schema drift")
    if props["production_publish_authorized"].get("const") is not False:
        fail("schema publication authority drift")

    if profile.get("profile_id") != "ruby-business-profile-v1":
        fail("profile id drift")
    if profile.get("public_domain") != "https://www.rubyscakedelights.shop/":
        fail("profile domain drift")
    if profile.get("source_site_role") != "reference-only":
        fail("profile source role drift")
    if profile.get("excluded_migration_sections") != ["products", "categories"]:
        fail("profile migration exclusions drift")
    if profile.get("profile_complete") is not True:
        fail("profile must remain 15/15 complete")
    if profile.get("production_publish_authorized") is not False:
        fail("profile must remain publish-gated")

    fields = {
        "store_information": {"business_name", "business_description", "address", "operating_hours", "pickup_instructions"},
        "contact_information": {"phone", "email", "instagram", "facebook", "other_contact"},
        "policies": {"privacy_policy", "terms_conditions", "cancellation_refund_policy", "pickup_order_policy", "allergen_disclaimer"},
    }
    verified = not_applicable = resolved = total = 0
    for section, expected in fields.items():
        records = profile.get(section)
        if not isinstance(records, dict) or set(records) != expected:
            fail(f"field set drift: {section}")
        for field, record in records.items():
            total += 1
            status = record.get("verification_status")
            if status == "verified":
                if record.get("source") != "user_confirmed" or not record.get("verified_at") or not record.get("verified_by"):
                    fail(f"verified metadata/source drift: {section}.{field}")
                if not isinstance(record.get("value"), str) or not record["value"].strip():
                    fail(f"verified value missing: {section}.{field}")
                verified += 1
                resolved += 1
            elif status == "not_applicable":
                if record.get("source") != "user_confirmed" or not record.get("verified_at") or not record.get("verified_by") or not record.get("notes"):
                    fail(f"N/A decision incomplete: {section}.{field}")
                not_applicable += 1
                resolved += 1
            else:
                fail(f"unresolved profile field: {section}.{field}={status!r}")

    if (verified, not_applicable, resolved, total) != (13, 2, 15, 15):
        fail(f"profile count drift verified={verified} n/a={not_applicable} resolved={resolved} total={total}")

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

    if "mid-September 2026" not in profile["store_information"]["operating_hours"].get("notes", ""):
        fail("operating-hours recheck safeguard missing")

    for field in ("privacy_policy", "terms_conditions", "cancellation_refund_policy", "pickup_order_policy", "allergen_disclaimer"):
        if profile["policies"][field].get("verification_status") != "verified":
            fail(f"policy approval drift: {field}")

    require(FORM.read_text(encoding="utf-8"), (
        "PROFILE CONTENT COMPLETE — 15/15 RESOLVED / PRODUCTION PUBLICATION STILL GATED",
        "Resolved: **15 / 15**",
        "profile_complete: true",
        "production_publish_authorized` remains **false**",
        "PHIL_AI_OS_RUBY_BUSINESS_PROFILE_15_OF_15_RESOLVED_PROFILE_COMPLETE_PUBLISH_GATED",
    ), "verification form")

    require(POLICY_APPROVAL.read_text(encoding="utf-8"), (
        "Section 1 — Privacy Policy: APPROVED / VERIFIED",
        "Section 2 — Terms & Conditions: APPROVED / VERIFIED",
        "PHIL_AI_OS_RUBY_PRIVACY_TERMS_APPROVED_PROFILE_15_OF_15_PUBLISH_GATED",
    ), "privacy/terms approval record")

    require(POLICY_TEXT.read_text(encoding="utf-8"), (
        "Act on the Protection of Personal Information (APPI)",
        "KOMOJU",
        "Nothing in these Terms is intended to exclude or restrict customer rights",
        "cross-contact may occur",
        "特定商取引法に基づく表記",
    ), "approved privacy/terms source")

    require(CUSTOMER_CONTENT.read_text(encoding="utf-8"), (
        "BUSINESS DESCRIPTION + 3 POLICIES APPROVED",
        "September 13, 2026",
        "PHIL_AI_OS_RUBY_CUSTOMER_CONTENT_DESCRIPTION_AND_3_POLICIES_APPROVED",
    ), "approved customer content")

    source = TOKUSHOHO_SOURCE.read_text(encoding="utf-8")
    require(source, (
        "https://www.rubyscakedelights.shop/commerce-disclosure",
        "BOMBEO PHILIP GO",
        "080-4355-7227",
        "rubyscakedelights@gmail.com",
        "info@rubyscakedelights.shop",
        "ヤマト運輸",
        "1,350円",
        "1,500円〜1,800円",
        "VISA, Mastercard, JCB, American Express, Diners Club",
        "legacy_source_content_captured: true",
        "PHIL_AI_OS_RUBY_TOKUSHOHO_LEGACY_SOURCE_CAPTURED_EMAIL_CORRECTION_APPROVED",
    ), "legacy Tokushoho source capture")

    tokushoho = TOKUSHOHO.read_text(encoding="utf-8")
    require(tokushoho, (
        "SOURCE CAPTURED / RECONCILED WORKING DRAFT — CEO APPROVAL REQUIRED BEFORE PUBLICATION",
        "BOMBEO PHILIP GO",
        "Ruby's Cake Delights",
        "050-1785-0575",
        "info@rubyscakedelights.shop",
        "order@rubyscakedelights.shop",
        "ヤマト運輸（クール宅急便）",
        "関東：一律 1,350円",
        "その他の地域：1,500円〜1,800円",
        "VISA",
        "Diners Club",
        "通常、ご注文日より2日〜5日以内に発送します。",
        "店舗受取",
        "商品到着後24時間以内",
        "tokushoho_source_reconciled: true",
        "tokushoho_publication_approved: false",
        "production_publish_authorized: false",
        "PHIL_AI_OS_RUBY_TOKUSHOHO_SOURCE_RECONCILED_EMAIL_UPDATED_PUBLICATION_PENDING_APPROVAL",
    ), "reconciled Tokushoho draft")

    publication_section = tokushoho.split("# 2. Proposed production disclosure — Japanese", 1)[1]
    if "rubyscakedelights@gmail.com" in publication_section:
        fail("legacy Gmail address must not remain in publication candidate")

    print("PHIL_AI_OS_RUBY_BUSINESS_PROFILE_TEMPLATE_GREEN fields=15 verified=13 not_applicable=2 resolved=15 profile_complete=true publish_authorized=false")
    print("PHIL_AI_OS_RUBY_BUSINESS_PROFILE_15_OF_15_GREEN unresolved=0")
    print("PHIL_AI_OS_RUBY_TOKUSHOHO_LEGACY_SOURCE_GREEN captured=true automated_retrieval=false")
    print("PHIL_AI_OS_RUBY_TOKUSHOHO_RECONCILIATION_GREEN seller=preserved email=current phone=current shipping=preserved pickup=added")
    print("PHIL_AI_OS_RUBY_TOKUSHOHO_PUBLICATION_BOUNDARY_GREEN approved=false publish_authorized=false")
    print("PHIL_AI_OS_RUBY_BUSINESS_PROFILE_MIGRATION_BOUNDARY_GREEN copy=store_contact_policies exclude=products_categories")


if __name__ == "__main__":
    main()

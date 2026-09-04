#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
from datetime import datetime
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/cx/final-confirmation-screen-evidence.schema.json"
TEMPLATE = ROOT / "ops/readiness/ruby-actual-woocommerce-final-confirmation-screen-evidence.template.json"

EXPECTED_VERSION = "ruby-woocommerce-final-confirmation-screen-evidence-v1"
ALLOWED_CAPTURE_METHODS = {"manual_browser_sanitized", "browser_screenshot_and_dom_notes"}
REQUIRED_OBSERVATIONS = (
    "product_name_quantity_options_visible",
    "subtotal_shipping_total_visible",
    "payment_method_visible",
    "payment_timing_or_deadline_visible",
    "fulfillment_timing_visible",
    "cancellation_returns_terms_visible_or_linked",
    "correction_path_available_before_submission",
    "final_action_label_unambiguous",
    "final_action_not_invoked",
    "tokushoho_disclosure_visible_or_linked",
    "tax_display_matches_exempt_posture",
    "konbini_three_day_deadline_reconciled_when_selected",
)
AUTHORITY_FIELDS = (
    "order_creation_authorized",
    "payment_execution_authorized",
    "production_publish_authorized",
    "catalog_mutation_authorized",
    "dns_cutover_authorized",
)
SENSITIVE_PATTERNS = {
    "WooCommerce credential": re.compile(r"\b(?:ck|cs)_[A-Za-z0-9]{8,}\b", re.I),
    "KOMOJU key": re.compile(r"\b(?:sk|pk)_(?:test|live)_[A-Za-z0-9_-]{6,}\b", re.I),
    "bearer token": re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b", re.I),
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "Japanese phone-like number": re.compile(r"(?<!\d)0\d{1,4}[- ]?\d{1,4}[- ]?\d{3,4}(?!\d)"),
    "session/cookie token": re.compile(r"\b(?:PHPSESSID|wordpress_logged_in|wp_woocommerce_session|woocommerce_cart_hash)\b", re.I),
}


class EvidenceRejected(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceRejected(message)


def parse_iso8601(value: object) -> None:
    require(isinstance(value, str) and value.strip(), "captured_at must be populated")
    text = value.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(text)
    except ValueError as exc:
        raise EvidenceRejected("captured_at must be ISO-8601") from exc


def assert_no_sensitive_text(value: object, context: str) -> None:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    for label, pattern in SENSITIVE_PATTERNS.items():
        require(pattern.search(text) is None, f"{context} contains forbidden {label}")


def validate_schema_boundary() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]
    require(props["version"].get("const") == EXPECTED_VERSION, "schema version drift")
    require(props["environment"].get("const") == "preproduction", "schema environment must remain preproduction")
    require(props["source_url_class"].get("const") == "sanitized_preproduction_checkout", "schema source class drift")
    require(props["synthetic_customer_data_only"].get("const") is True, "schema must require synthetic-only data")
    require(props["contains_personal_data"].get("const") is False, "schema must forbid retained PII")
    require(props["contains_secret_material"].get("const") is False, "schema must forbid secret material")
    require(props["observations"]["properties"]["final_action_not_invoked"].get("const") is True, "schema must lock final action uninvoked")
    for field in AUTHORITY_FIELDS:
        require(props["authority"]["properties"][field].get("const") is False, f"schema authority expanded: {field}")


def validate_completed_evidence(data: dict) -> None:
    require(isinstance(data, dict), "evidence must be an object")
    require(data.get("version") == EXPECTED_VERSION, "evidence version drift")
    evidence_id = data.get("evidence_id")
    require(isinstance(evidence_id, str) and evidence_id.strip() and evidence_id != "pending", "completed evidence requires a non-pending evidence_id")
    require(data.get("environment") == "preproduction", "completed evidence must be preproduction-only")
    require(data.get("capture_method") in ALLOWED_CAPTURE_METHODS, "unsupported capture method")
    parse_iso8601(data.get("captured_at"))
    require(data.get("source_url_class") == "sanitized_preproduction_checkout", "source URL class drift")
    require(data.get("synthetic_customer_data_only") is True, "real customer data is forbidden")
    require(data.get("contains_personal_data") is False, "evidence may not retain personal data")
    require(data.get("contains_secret_material") is False, "evidence may not retain secret material")

    captures = data.get("screen_capture_refs")
    require(isinstance(captures, list) and 1 <= len(captures) <= 8, "completed evidence requires 1-8 sanitized screen captures")
    seen_hashes: set[str] = set()
    for index, capture in enumerate(captures):
        require(isinstance(capture, dict), f"capture {index} must be an object")
        ref = capture.get("artifact_ref")
        digest = capture.get("sha256")
        require(isinstance(ref, str) and ref.strip(), f"capture {index} artifact_ref missing")
        require(not ref.lower().startswith(("http://", "https://")), f"capture {index} must use a non-web artifact reference")
        require("?" not in ref and "#" not in ref, f"capture {index} artifact reference may not contain query/fragment data")
        require(isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest) is not None, f"capture {index} SHA-256 invalid")
        require(digest not in seen_hashes, f"capture {index} duplicates a prior SHA-256")
        seen_hashes.add(digest)
        require(capture.get("contains_personal_data") is False, f"capture {index} contains PII")
        require(capture.get("contains_secret_material") is False, f"capture {index} contains secret material")
        require(isinstance(capture.get("redaction_applied"), bool), f"capture {index} redaction flag missing")
        assert_no_sensitive_text(ref, f"capture {index} artifact_ref")

    observations = data.get("observations")
    require(isinstance(observations, dict), "observations object missing")
    require(set(observations) == set(REQUIRED_OBSERVATIONS), "observation key set drift")
    for field in REQUIRED_OBSERVATIONS:
        require(observations.get(field) is True, f"required actual-screen observation not GREEN: {field}")

    authority = data.get("authority")
    require(isinstance(authority, dict), "authority object missing")
    require(set(authority) == set(AUTHORITY_FIELDS), "authority key set drift")
    for field in AUTHORITY_FIELDS:
        require(authority.get(field) is False, f"authority expanded unexpectedly: {field}")

    notes = data.get("review_notes", [])
    require(isinstance(notes, list) and all(isinstance(item, str) for item in notes), "review_notes must be a string list")
    assert_no_sensitive_text(notes, "review_notes")
    require(data.get("evidence_complete") is True, "completed evidence must set evidence_complete=true")
    require(data.get("actual_final_confirmation_screen_reviewed") is True, "completed evidence must explicitly record actual-screen review")


def build_self_test_evidence() -> dict:
    pending = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    sample = copy.deepcopy(pending)
    sample["evidence_id"] = "self-test-synthetic-evidence"
    sample["capture_method"] = "browser_screenshot_and_dom_notes"
    sample["captured_at"] = "2026-09-04T00:00:00Z"
    sample["screen_capture_refs"] = [{
        "artifact_ref": "artifact://sanitized/self-test-final-screen.png",
        "sha256": "a" * 64,
        "redaction_applied": True,
        "contains_personal_data": False,
        "contains_secret_material": False,
    }]
    sample["observations"] = {key: True for key in REQUIRED_OBSERVATIONS}
    sample["review_notes"] = ["Synthetic harness self-test only; no external screen or transaction was used."]
    sample["evidence_complete"] = True
    sample["actual_final_confirmation_screen_reviewed"] = True
    return sample


def self_test() -> None:
    validate_schema_boundary()
    pending = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    try:
        validate_completed_evidence(pending)
    except EvidenceRejected:
        pass
    else:
        raise EvidenceRejected("pending template was incorrectly accepted as completed evidence")

    sample = build_self_test_evidence()
    validate_completed_evidence(sample)

    unsafe = copy.deepcopy(sample)
    unsafe["review_notes"] = ["customer@example.com"]
    try:
        validate_completed_evidence(unsafe)
    except EvidenceRejected:
        pass
    else:
        raise EvidenceRejected("PII-like review note was incorrectly accepted")

    authorized = copy.deepcopy(sample)
    authorized["authority"]["payment_execution_authorized"] = True
    try:
        validate_completed_evidence(authorized)
    except EvidenceRejected:
        pass
    else:
        raise EvidenceRejected("expanded payment authority was incorrectly accepted")

    print("PHIL_AI_OS_RUBY_ACTUAL_FINAL_SCREEN_EVIDENCE_ACCEPTANCE_HARNESS_GREEN self_test=true transaction=false")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a completed sanitized actual WooCommerce final-screen evidence pack.")
    parser.add_argument("evidence_json", nargs="?", help="Path to completed evidence JSON")
    parser.add_argument("--self-test", action="store_true", help="Run non-transactional in-memory acceptance/rejection tests")
    args = parser.parse_args()

    try:
        if args.self_test:
            self_test()
            return 0
        require(args.evidence_json is not None, "evidence JSON path is required unless --self-test is used")
        validate_schema_boundary()
        path = Path(args.evidence_json)
        require(path.is_file(), f"evidence file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        validate_completed_evidence(data)
        print("PHIL_AI_OS_RUBY_ACTUAL_WOOCOMMERCE_FINAL_SCREEN_EVIDENCE_GREEN evidence_complete=true payment_execution=false")
        return 0
    except (EvidenceRejected, json.JSONDecodeError) as exc:
        raise SystemExit(f"PHIL_AI_OS_RUBY_ACTUAL_FINAL_SCREEN_EVIDENCE_REJECTED: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())

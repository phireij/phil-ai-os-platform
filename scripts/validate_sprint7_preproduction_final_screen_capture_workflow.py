#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ruby-preproduction-final-screen-capture.yml"
PROBE = ROOT / "scripts/probe_ruby_preproduction_catalog.mjs"
CAPTURE = ROOT / "scripts/capture_ruby_preproduction_final_screen.mjs"
ATTEMPT_VALIDATOR = ROOT / "scripts/validate_sprint7_preproduction_final_screen_capture_attempt.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_RUBY_PREPRODUCTION_FINAL_SCREEN_CAPTURE_WORKFLOW_FAILED: {message}")


def main() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    probe = PROBE.read_text(encoding="utf-8")
    capture = CAPTURE.read_text(encoding="utf-8")

    require("workflow_dispatch:" in workflow, "capture workflow must remain manual-only")
    require("pull_request:" not in workflow and "push:" not in workflow and "schedule:" not in workflow, "capture workflow gained automatic trigger")
    require("confirm_preproduction_only:" in workflow, "preproduction confirmation input missing")
    require("confirm_no_order_submission:" in workflow, "no-order confirmation input missing")
    require("inputs.confirm_preproduction_only == true && inputs.confirm_no_order_submission == true" in workflow, "job confirmation gate drift")
    require("permissions:\n  contents: read" in workflow, "workflow permissions must remain contents:read")
    require("https://darkgreen-wallaby-680439.hostingersite.com" in workflow, "preproduction target lock missing")
    require("GET-only preflight for a usable preproduction catalog item" in workflow, "catalog fast preflight missing")
    require("node scripts/probe_ruby_preproduction_catalog.mjs" in workflow, "catalog probe invocation missing")
    require(workflow.index("node scripts/probe_ruby_preproduction_catalog.mjs") < workflow.index("playwright@1.62.1"), "catalog probe must run before Playwright installation")
    require("catalog-probe.json" in workflow, "catalog blocker evidence is not retained")
    require("PHIL_AI_OS_RUBY_PREPRODUCTION_CATALOG_BLOCKER_EVIDENCE_GREEN" in workflow, "catalog blocker evidence marker missing")
    require("playwright@1.62.1" in workflow, "Playwright version must remain pinned")
    require("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow, "artifact action must remain SHA-pinned")
    require("retention-days: 1" in workflow, "sanitized capture retention must remain one day")
    require("if-no-files-found: warn" in workflow, "partial safety evidence must remain uploadable after a failed capture")
    for phrase in (
        "probe['network_read_only'] is True",
        "probe['mutation_authorized'] is False",
        "probe['order_creation_authorized'] is False",
        "probe['payment_execution_authorized'] is False",
        "draft['evidence_complete'] is False",
        "draft['actual_final_confirmation_screen_reviewed'] is False",
        "draft['observations']['final_action_not_invoked'] is True",
        "all(value is False for value in draft['authority'].values())",
        "summary['final_action_invoked'] is False",
        "summary['blocked_dangerous_request_count'] == 0",
        "summary['payment_execution_authorized'] is False",
    ):
        require(phrase in workflow, f"fail-closed assertion missing: {phrase}")

    require('const EXPECTED_HOST = "darkgreen-wallaby-680439.hostingersite.com"' in probe, "probe host allowlist drift")
    require("target.protocol !== \"https:\" || target.hostname !== EXPECTED_HOST" in probe, "probe HTTPS/host guard missing")
    require('method: "GET"' in probe, "probe must explicitly use GET")
    require("woocommerce_store_api_products_get_only" in probe, "probe endpoint classification missing")
    require("network_read_only: true" in probe, "probe must record read-only network scope")
    require("mutation_authorized: false" in probe, "probe mutation authority must remain false")
    require("order_creation_authorized: false" in probe, "probe order authority must remain false")
    require("payment_execution_authorized: false" in probe, "probe payment authority must remain false")
    require("production_publish_authorized: false" in probe, "probe publication authority must remain false")
    require("fetch(endpoint" in probe, "probe must use the public Store API GET surface")
    require(".post(" not in probe and 'method: "POST"' not in probe, "probe gained POST capability")
    require(".put(" not in probe and 'method: "PUT"' not in probe, "probe gained PUT capability")
    require(".patch(" not in probe and 'method: "PATCH"' not in probe, "probe gained PATCH capability")
    require(".delete(" not in probe and 'method: "DELETE"' not in probe, "probe gained DELETE capability")

    require('const EXPECTED_HOST = "darkgreen-wallaby-680439.hostingersite.com"' in capture, "capture script host allowlist drift")
    require("target.protocol !== \"https:\" || target.hostname !== EXPECTED_HOST" in capture, "HTTPS/host target guard missing")
    require("woocommerce_place_order_ajax_blocked" in capture, "classic WooCommerce place-order block missing")
    require("woocommerce_order_endpoint_blocked" in capture, "WooCommerce Store/REST order endpoint block missing")
    require("komoju_post_blocked" in capture, "KOMOJU non-GET block missing")
    require("external_post_blocked" in capture, "external POST block missing")
    require("forbidden_method_${method}" in capture, "PUT/PATCH/DELETE block missing")
    require("final_action_invoked: false" in capture, "capture must record final action uninvoked")
    require("evidence_complete: false" in capture, "capture must emit draft evidence only")
    require("actual_final_confirmation_screen_reviewed: false" in capture, "capture cannot self-approve actual screen")
    require("payment_execution_authorized: false" in capture, "payment authority must remain false")
    require("blockedRequests.length !== 0" in capture, "dangerous-request fail-closed assertion missing")
    require(".click(" not in capture, "capture script must never click a UI control")
    require("context.request.post(" not in capture, "capture script must not issue direct POST requests")
    require("page.request.post(" not in capture, "capture script must not issue page request POSTs")

    forbidden = {
        "WooCommerce production key": r"\b(?:ck|cs)_[A-Za-z0-9]{8,}\b",
        "KOMOJU key": r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9_-]{6,}\b",
        "authorizing payment flag": r"payment_execution_authorized\s*[:=]\s*true",
        "authorizing order flag": r"order_creation_authorized\s*[:=]\s*true",
    }
    combined = workflow + "\n" + probe + "\n" + capture
    for label, pattern in forbidden.items():
        require(re.search(pattern, combined, flags=re.I) is None, f"forbidden {label} found")

    require(ATTEMPT_VALIDATOR.exists(), "capture-attempt validator missing")
    subprocess.run([sys.executable, str(ATTEMPT_VALIDATOR)], check=True)

    print("PHIL_AI_OS_RUBY_PREPRODUCTION_FINAL_SCREEN_CAPTURE_WORKFLOW_GREEN manual_only=true preflight_get_only=true preproduction=true no_order=true payment_execution=false")


if __name__ == "__main__":
    main()

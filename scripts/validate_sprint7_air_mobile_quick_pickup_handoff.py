#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "ops/readiness/ruby-air-mobile-quick-pickup-url.template.json"
ROADMAP = ROOT / "docs/MASTER_EXECUTIVE_ROADMAP_SCHEDULE_CONTROL.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_AIR_MOBILE_QUICK_PICKUP_HANDOFF_FAILED: {message}")


def main() -> None:
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    roadmap = ROADMAP.read_text(encoding="utf-8")

    require(data.get("version") == "ruby-air-mobile-quick-pickup-url-v1", "schema drift")
    require(data.get("dependency_class") == "later_launch_input", "dependency classification drift")
    require(data.get("blocks_sprint3_closure") is False, "Air Mobile URL incorrectly became Sprint 3 closure blocker")
    require(data.get("service") == "Air Mobile Order Quick Pickup", "service name drift")

    url = data.get("production_url")
    status = data.get("url_status")
    owner_confirmed = data.get("owner_confirmed")
    if url is None:
        require(status == "pending_owner_input", "missing URL must remain pending owner input")
        require(owner_confirmed is False, "missing URL cannot be owner-confirmed")
        require(data.get("owner_confirmation_ref") is None, "missing URL cannot have confirmation ref")
        require(data.get("decision") == "AIR_MOBILE_QUICK_PICKUP_URL_PENDING_OWNER_INPUT_FAIL_CLOSED", "pending decision drift")
    else:
        require(isinstance(url, str) and url.strip() == url and url, "production URL must be a non-empty trimmed string")
        parsed = urlparse(url)
        require(parsed.scheme == "https", "production URL must use https")
        require(bool(parsed.netloc), "production URL must have a host")
        require(parsed.username is None and parsed.password is None, "credentials must not be embedded in URL")
        require(parsed.fragment == "", "production URL must not depend on a fragment")
        require(owner_confirmed is True, "provided production URL must be owner-confirmed")
        require(bool(data.get("owner_confirmation_ref")), "provided production URL requires owner confirmation reference")
        require(status in {"owner_confirmed_pending_validation", "validated_ready_for_controlled_activation"}, "provided URL status invalid")

    validation = data["validation"]
    for key in (
        "https_required",
        "public_http_reachability_required_before_launch",
        "customer_facing_page_review_required",
        "pickup_flow_review_required",
        "bilingual_copy_review_required_if_exposed_in_ruby_cx",
        "no_credentials_embedded_in_url",
        "redirect_chain_review_required",
    ):
        require(validation.get(key) is True, f"validation control regressed: {key}")

    integration = data["integration"]
    require(integration.get("production_link_activation_authorized") is False, "production link activation authority expanded")
    require(integration.get("automatic_link_publication_authorized") is False, "automatic link publication authority expanded")
    if url is None:
        require(integration.get("cx_link_activation_ready") is False, "CX link cannot be ready without URL")
        require(integration.get("operations_reference_ready") is False, "operations reference cannot be ready without URL")

    for key, value in data["authority"].items():
        require(value is False, f"authority expanded unexpectedly: {key}")

    require("Provide the Air Mobile Order Quick Pickup production URL when available" in roadmap, "roadmap dependency statement missing")
    require("does not prevent the current Sprint 3 owner-input gate" in roadmap, "roadmap Sprint 3 boundary statement missing")

    print("PHIL_AI_OS_AIR_MOBILE_QUICK_PICKUP_HANDOFF_GREEN pending_owner_input=true sprint3_blocker=false authority=false")


if __name__ == "__main__":
    main()

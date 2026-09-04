#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "ops/readiness/ruby-tokushoho-owner-approval.template.json"
CANDIDATE = ROOT / "ops/readiness/ruby-tokushoho-publication-candidate-2026-09-04.json"
DOC = ROOT / "docs/RUBY_TOKUSHOHO_FINAL_PUBLICATION_CANDIDATE_2026-09-04.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_TOKUSHOHO_OWNER_APPROVAL_HANDOFF_FAILED: {message}")


def main() -> None:
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    require(template["version"] == "ruby-tokushoho-owner-approval-v1", "template version drift")
    require(template["candidate_ref"] == "ops/readiness/ruby-tokushoho-publication-candidate-2026-09-04.json", "candidate ref drift")
    require(template["candidate_document_ref"] == "docs/RUBY_TOKUSHOHO_FINAL_PUBLICATION_CANDIDATE_2026-09-04.md", "candidate document ref drift")
    require(DOC.is_file(), "candidate document missing")
    require(candidate["candidate"]["publication_candidate_ready"] is True, "candidate is no longer ready")
    require(candidate["approval_and_publication"]["owner_publication_approval_recorded"] is False, "canonical candidate unexpectedly records owner approval")
    require(candidate["approval_and_publication"]["published"] is False, "candidate unexpectedly published")

    require(template["decision_scope"] == "candidate_text_approval_only", "approval scope expanded")
    require(template["decision_status"] == "pending", "template must remain pending")
    require(template["approval_recorded"] is False, "template cannot self-record approval")
    require(template["candidate_text_approved"] is False, "template cannot self-approve candidate text")
    require(template["decision_by_role"] == "CEO", "decision role drift")
    require(template["decision_by"] is None, "template cannot invent decision maker")
    require(template["decision_at"] is None, "template cannot invent decision time")

    acknowledgements = template["acknowledgements"]
    for key, value in acknowledgements.items():
        require(value is True, f"required approval acknowledgement missing: {key}")

    for key, value in template["authority"].items():
        require(value is False, f"approval handoff expanded authority: {key}")

    require(template["decision"] == "TOKUSHOHO_OWNER_APPROVAL_PENDING_FAIL_CLOSED", "decision marker drift")
    print("PHIL_AI_OS_TOKUSHOHO_OWNER_APPROVAL_HANDOFF_GREEN pending=true publication_execution=false payment_execution=false")


if __name__ == "__main__":
    main()

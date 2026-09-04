#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "ops/readiness/ruby-tokushoho-owner-approval-2026-09-04.json"
CANDIDATE = ROOT / "ops/readiness/ruby-tokushoho-publication-candidate-2026-09-04.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_TOKUSHOHO_OWNER_APPROVAL_RECORD_FAILED: {message}")


def main() -> None:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    require(record["decision_scope"] == "candidate_text_approval_only", "approval scope expanded")
    require(record["decision_status"] == "approved", "approval not recorded as approved")
    require(record["approval_recorded"] is True, "approval_recorded must be true")
    require(record["candidate_text_approved"] is True, "candidate text must be approved")
    require(record["decision_by_role"] == "CEO", "decision role drift")
    require(bool(record["decision_at"]), "decision timestamp missing")

    for key, value in record["acknowledgements"].items():
        require(value is True, f"required acknowledgement missing: {key}")
    for key, value in record["authority"].items():
        require(value is False, f"approval record expanded authority: {key}")

    approval = candidate["approval_and_publication"]
    require(approval["candidate_text_approval_recorded"] is True, "candidate text approval not reconciled")
    require(approval["candidate_text_approved"] is True, "candidate text approval false")
    require(approval["candidate_text_approval_ref"] == "ops/readiness/ruby-tokushoho-owner-approval-2026-09-04.json", "approval ref drift")
    require(approval["owner_publication_approval_recorded"] is False, "publication approval must remain false")
    require(approval["tokushoho_publication_approved"] is False, "publication must remain unapproved")
    require(approval["published"] is False, "candidate must remain unpublished")

    for key, value in candidate["authority"].items():
        require(value is False, f"candidate authority expanded: {key}")

    require(record["decision"] == "TOKUSHOHO_CANDIDATE_TEXT_APPROVED_PUBLICATION_EXECUTION_PENDING_FAIL_CLOSED", "record decision drift")
    print("PHIL_AI_OS_TOKUSHOHO_OWNER_APPROVAL_RECORD_GREEN candidate_text_approved=true publication_execution=false payment_execution=false")


if __name__ == "__main__":
    main()

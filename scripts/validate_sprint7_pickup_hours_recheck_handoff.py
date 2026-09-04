#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECHECK = ROOT / "ops/readiness/ruby-pickup-hours-mid-september-recheck.template.json"
CANDIDATE = ROOT / "ops/readiness/ruby-tokushoho-publication-candidate-2026-09-04.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_PICKUP_HOURS_RECHECK_HANDOFF_FAILED: {message}")


def main() -> None:
    data = json.loads(RECHECK.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    require(data.get("version") == "ruby-pickup-hours-mid-september-recheck-v1", "schema drift")
    require(data.get("recheck_window") == "mid_september_2026", "recheck window drift")
    require(data.get("recheck_required") is True, "recheck requirement lost")
    require(candidate["candidate"]["pickup_hours_recheck_required_mid_september"] is True, "candidate no longer requires mid-September pickup recheck")

    reference = data["current_reference"]
    require(reference["pickup_days"] == ["wednesday", "thursday", "friday", "saturday"], "reference pickup days drift")
    require(reference["pickup_start_local"] == "14:00", "reference pickup start drift")
    require(reference["pickup_end_local"] == "20:00", "reference pickup end drift")
    require(reference["timezone"] == "Asia/Tokyo", "pickup timezone drift")

    confirmation = data["owner_or_operator_confirmation"]
    cx = data["customer_experience"]
    if data["recheck_completed"] is False:
        require(reference["status"] == "reference_only_pending_recheck", "unrechecked hours must remain reference-only")
        require(confirmation["confirmed"] is False, "pending recheck cannot be confirmed")
        require(confirmation["confirmed_by"] is None, "pending recheck cannot name confirmer")
        require(confirmation["confirmed_at"] is None, "pending recheck cannot have confirmation time")
        require(confirmation["evidence_ref"] is None, "pending recheck cannot have evidence ref")
        require(cx["copy_revalidated"] is False, "CX copy cannot be revalidated before pickup recheck")
        require(cx["pickup_selector_revalidated"] is False, "pickup selector cannot be revalidated before pickup recheck")
        require(cx["tokushoho_pickup_wording_revalidated"] is False, "Tokushoho pickup wording cannot be revalidated before pickup recheck")
        require(data["decision"] == "PICKUP_HOURS_MID_SEPTEMBER_RECHECK_PENDING_FAIL_CLOSED", "pending decision drift")
    else:
        require(confirmation["confirmed"] is True, "completed recheck requires confirmation")
        require(bool(confirmation["confirmed_by"]), "completed recheck requires confirmer")
        require(bool(confirmation["confirmed_at"]), "completed recheck requires confirmation timestamp")
        require(bool(confirmation["evidence_ref"]), "completed recheck requires evidence reference")

    require(cx["production_copy_update_authorized"] is False, "recheck must not itself authorize production copy mutation")
    for key, value in data["authority"].items():
        require(value is False, f"authority expanded unexpectedly: {key}")

    print("PHIL_AI_OS_PICKUP_HOURS_RECHECK_HANDOFF_GREEN recheck_pending=true production_mutation=false")


if __name__ == "__main__":
    main()

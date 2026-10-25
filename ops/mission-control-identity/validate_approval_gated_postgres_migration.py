#!/usr/bin/env python3
"""Static guard for the unapplied approval-gated PostgreSQL foundation."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent
MIGRATION = ROOT / "postgres" / "001_approval_gated_foundation.sql"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"APPROVAL_GATED_POSTGRES_MIGRATION_INVALID: {message}")


def main() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    normalized = source.lower()
    require("design only" in normalized and "not approved for application" in normalized, "migration must remain explicitly unapplied")
    require(normalized.lstrip().startswith("-- design only") and "begin;" in normalized and normalized.rstrip().endswith("commit;"), "migration transaction boundary missing")
    for table in ("approval_gated_missions", "approval_gated_plans", "approval_packets", "approval_gated_audit_events"):
        require(f"mission_control.{table}" in normalized, f"required table missing: {table}")
    require(normalized.count("check (execution_authorized is false)") == 4, "execution must be constrained false in every table")
    require(normalized.count("check (mutation_authorized is false)") == 4, "mutation must be constrained false in every table")
    require(normalized.count("check (authority_effect = 'none')") == 4, "authority effect must be constrained none in every table")
    require("decision_state = 'awaiting_decision'" in normalized, "approval decision must remain inactive")
    require("previous_event_hash" in normalized and "event_hash" in normalized and "content_included is false" in normalized, "audit hash/content boundary missing")
    forbidden = ("grant ", "revoke ", "insert into", "update ", "delete from", "copy ", "password", "connection string", "database_url")
    for token in forbidden:
        require(token not in normalized, f"forbidden deployment or secret content: {token.strip()}")
    print("APPROVAL_GATED_POSTGRES_MIGRATION_GREEN status=design_only_inactive authority_effect=none execution=false mutation=false")


if __name__ == "__main__":
    main()

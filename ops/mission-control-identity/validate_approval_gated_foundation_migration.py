#!/usr/bin/env python3
"""Static guard for the unapplied approval-gated foundation schema.

The schema remains a design artifact until a separately authorized deployment
process applies it.  This validator prevents a future edit from silently
adding authority, deployment commands, or sensitive persistence.
"""

from __future__ import annotations

from pathlib import Path


MIGRATION = Path(__file__).resolve().parent / "postgres" / "001_approval_gated_foundation.sql"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"APPROVAL_GATED_FOUNDATION_MIGRATION_INVALID: {message}")


def main() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    normalized = source.lower()

    require("design only" in normalized and "not approved for application" in normalized, "migration must remain unapplied")
    require("create schema if not exists mission_control" in normalized, "mission_control schema missing")
    for table in (
        "mission_control.approval_gated_missions",
        "mission_control.approval_gated_plans",
        "mission_control.approval_packets",
        "mission_control.approval_gated_audit_events",
    ):
        require(table in normalized, f"required table missing: {table}")

    require(normalized.count("check (execution_authorized is false)") == 4, "execution must be constrained false")
    require(normalized.count("check (mutation_authorized is false)") == 4, "mutation must be constrained false")
    require(normalized.count("check (authority_effect = 'none')") == 4, "authority effect must be constrained none")

    for token in (
        "raw_subject text",
        "bearer_token",
        "signing_key bytea",
        "access_token text",
        "authorization_code text",
        "insert into",
        "update ",
        "delete from",
        "grant ",
        "revoke ",
        "alter role",
        "create role",
        "create database",
    ):
        require(token not in normalized, f"forbidden sensitive or deployment content: {token.strip()}")

    print("APPROVAL_GATED_FOUNDATION_MIGRATION_GREEN status=design_only_inactive authority_effect=none")


if __name__ == "__main__":
    main()

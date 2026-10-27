#!/usr/bin/env python3
"""Static guard for the unapplied R3 attestation-handoff schema."""

from __future__ import annotations

from pathlib import Path


MIGRATION = Path(__file__).resolve().parent / "postgres" / "002_r3_reauthentication_attestation_handoff.sql"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"R3_ATTESTATION_HANDOFF_MIGRATION_INVALID: {message}")


def main() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    normalized = source.lower()
    require("design only" in normalized and "not approved for application" in normalized, "migration must remain unapplied")
    require("mission_control.r3_reauthentication_attestations" in normalized, "attestation table missing")
    for field in ("issuer", "subject_sha256", "attestation_digest", "verification_id", "authenticated_at", "expires_at", "consumed_at", "retention_expires_at"):
        require(field in normalized, f"required metadata field missing: {field}")
    require(normalized.count("check (execution_authorized is false)") == 1, "execution must be constrained false")
    require(normalized.count("check (mutation_authorized is false)") == 1, "mutation must be constrained false")
    require(normalized.count("check (authority_effect = 'none')") == 1, "authority effect must be constrained none")
    for token in ("raw_subject text", "bearer_token", "signing_key bytea", "access_token text", "authorization_code text", "insert into", "update ", "delete from", "grant ", "revoke "):
        require(token not in normalized, f"forbidden sensitive or deployment content: {token.strip()}")
    print("R3_ATTESTATION_HANDOFF_MIGRATION_GREEN status=design_only_inactive authority_effect=none")


if __name__ == "__main__":
    main()

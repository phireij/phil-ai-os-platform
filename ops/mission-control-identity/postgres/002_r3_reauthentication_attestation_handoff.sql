-- DESIGN ONLY. This migration is not approved for application to any database.
-- It stores R3 attestation metadata only; it must never store a raw subject,
-- bearer proof, signing key, access token, authorization code, or action body.

BEGIN;

CREATE TABLE mission_control.r3_reauthentication_attestations (
    attestation_id TEXT PRIMARY KEY,
    issuer TEXT NOT NULL CHECK (issuer = 'https://accounts.google.com'),
    subject_sha256 TEXT NOT NULL CHECK (subject_sha256 ~ '^sha256:[a-f0-9]{64}$'),
    attestation_digest TEXT NOT NULL UNIQUE CHECK (attestation_digest ~ '^sha256:[a-f0-9]{64}$'),
    verification_id TEXT NOT NULL,
    authenticated_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    state TEXT NOT NULL CHECK (state IN ('issued', 'consumed', 'expired', 'revoked')),
    retention_expires_at TIMESTAMPTZ NOT NULL,
    execution_authorized BOOLEAN NOT NULL DEFAULT FALSE CHECK (execution_authorized IS FALSE),
    mutation_authorized BOOLEAN NOT NULL DEFAULT FALSE CHECK (mutation_authorized IS FALSE),
    authority_effect TEXT NOT NULL DEFAULT 'none' CHECK (authority_effect = 'none'),
    CHECK (expires_at > authenticated_at),
    CHECK (retention_expires_at >= expires_at)
);

COMMIT;

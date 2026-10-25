-- DESIGN ONLY. This migration is not approved for application to any database.
-- It creates no execution capability: all authority flags are constrained false.

BEGIN;

CREATE SCHEMA IF NOT EXISTS mission_control;

CREATE TABLE mission_control.approval_gated_missions (
    mission_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    project_id TEXT NOT NULL CHECK (project_id IN ('phil-ai-os', 'rubys-cake-delights-hq', 'kcfc-portal')),
    source TEXT NOT NULL CHECK (source IN ('ceo_conversation', 'project_signal', 'connected_channel')),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('R0', 'R1', 'R2', 'R3', 'R4')),
    required_gate TEXT NOT NULL CHECK (required_gate IN ('audit_only', 'ceo_approval', 'ceo_reauthenticate', 'ceo_typed_confirmation', 'blocked')),
    policy_version TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('draft', 'awaiting_approval', 'stopped_for_review', 'expired', 'revoked')),
    created_at TIMESTAMPTZ NOT NULL,
    execution_authorized BOOLEAN NOT NULL DEFAULT FALSE CHECK (execution_authorized IS FALSE),
    mutation_authorized BOOLEAN NOT NULL DEFAULT FALSE CHECK (mutation_authorized IS FALSE),
    authority_effect TEXT NOT NULL DEFAULT 'none' CHECK (authority_effect = 'none')
);

CREATE TABLE mission_control.approval_gated_plans (
    plan_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES mission_control.approval_gated_missions(mission_id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL CHECK (revision > 0),
    plan_digest TEXT NOT NULL CHECK (plan_digest ~ '^sha256:[a-f0-9]{64}$'),
    steps_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    execution_authorized BOOLEAN NOT NULL DEFAULT FALSE CHECK (execution_authorized IS FALSE),
    mutation_authorized BOOLEAN NOT NULL DEFAULT FALSE CHECK (mutation_authorized IS FALSE),
    authority_effect TEXT NOT NULL DEFAULT 'none' CHECK (authority_effect = 'none'),
    UNIQUE (mission_id, revision),
    UNIQUE (mission_id, plan_digest)
);

CREATE TABLE mission_control.approval_packets (
    approval_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES mission_control.approval_gated_missions(mission_id) ON DELETE RESTRICT,
    plan_id TEXT NOT NULL REFERENCES mission_control.approval_gated_plans(plan_id) ON DELETE RESTRICT,
    plan_digest TEXT NOT NULL CHECK (plan_digest ~ '^sha256:[a-f0-9]{64}$'),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('R1', 'R2', 'R3', 'R4')),
    required_gate TEXT NOT NULL CHECK (required_gate IN ('ceo_approval', 'ceo_reauthenticate', 'ceo_typed_confirmation', 'blocked')),
    policy_version TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    decision_state TEXT NOT NULL DEFAULT 'awaiting_decision' CHECK (decision_state = 'awaiting_decision'),
    created_at TIMESTAMPTZ NOT NULL,
    execution_authorized BOOLEAN NOT NULL DEFAULT FALSE CHECK (execution_authorized IS FALSE),
    mutation_authorized BOOLEAN NOT NULL DEFAULT FALSE CHECK (mutation_authorized IS FALSE),
    authority_effect TEXT NOT NULL DEFAULT 'none' CHECK (authority_effect = 'none'),
    UNIQUE (mission_id, plan_id)
);

CREATE TABLE mission_control.approval_gated_audit_events (
    event_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES mission_control.approval_gated_missions(mission_id) ON DELETE RESTRICT,
    plan_id TEXT REFERENCES mission_control.approval_gated_plans(plan_id) ON DELETE RESTRICT,
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    stage TEXT NOT NULL CHECK (stage IN ('intake_created', 'risk_assessed', 'plan_created', 'approval_requested', 'approval_expired', 'approval_revoked', 'preflight_stopped', 'exception_recorded')),
    occurred_at TIMESTAMPTZ NOT NULL,
    policy_version TEXT NOT NULL,
    previous_event_hash TEXT CHECK (previous_event_hash IS NULL OR previous_event_hash ~ '^sha256:[a-f0-9]{64}$'),
    event_hash TEXT NOT NULL CHECK (event_hash ~ '^sha256:[a-f0-9]{64}$'),
    content_included BOOLEAN NOT NULL DEFAULT FALSE CHECK (content_included IS FALSE),
    execution_authorized BOOLEAN NOT NULL DEFAULT FALSE CHECK (execution_authorized IS FALSE),
    mutation_authorized BOOLEAN NOT NULL DEFAULT FALSE CHECK (mutation_authorized IS FALSE),
    authority_effect TEXT NOT NULL DEFAULT 'none' CHECK (authority_effect = 'none'),
    UNIQUE (mission_id, sequence),
    UNIQUE (event_hash)
);

COMMIT;

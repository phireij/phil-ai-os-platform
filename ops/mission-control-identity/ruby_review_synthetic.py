"""Disabled-by-default, fixture-only Ruby review surface for Gate A.

This module intentionally has no store, transport, filesystem, or network
dependency.  The same-origin owner-session handler may expose this fixed
fixture only after an explicit runtime flag is supplied; it cannot read or
write real Ruby review records.
"""

from __future__ import annotations

import os
from typing import Any


RUBY_REVIEW_PROJECT = "rubys-cake-delights-hq"
SYNTHETIC_SURFACE_ENV = "MISSION_CONTROL_RUBY_REVIEW_SYNTHETIC_SURFACE_ENABLED"


def synthetic_surface_enabled() -> bool:
    """Return false unless the narrow fixture flag has its exact value."""
    return os.environ.get(SYNTHETIC_SURFACE_ENV) == "true"


def ruby_review_synthetic_surface() -> dict[str, Any]:
    """Return one fixed review fixture without accessing Core or customer data."""
    record_id = "ruby-review-fixture-0001"
    return {
        "schema": "ruby-review-synthetic.v1",
        "mode": "synthetic_fixture",
        "project_id": RUBY_REVIEW_PROJECT,
        "owner_access": "same_origin_session_only",
        "exports_enabled": False,
        "activation_authorized": False,
        "records": [{
            "record_id": record_id,
            "project_id": RUBY_REVIEW_PROJECT,
            "state": "pending_review",
            "revision_number": 1,
            "synthetic": True,
        }],
        "audit": [{
            "event_id": "ruby-review-fixture-audit-0001",
            "record_id": record_id,
            "event_type": "record_created",
            "identifier_only": True,
            "synthetic": True,
        }],
        "authority_effect": "none",
        "execution_authorized": False,
        "mutation_authorized": False,
    }

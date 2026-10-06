#!/usr/bin/env python3
"""Validate A1 matrix remains bounded and preactivation is fail-closed."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
M=ROOT/"ops/authorizations/a1-authority-matrix.v1.json"
REQUIRED_DENY={"pull_request_merge","production_publish_or_cutover","dns_change","real_order_creation","payment_or_refund_execution","live_customer_messaging","credential_or_secret_mutation","authority_matrix_self_widening"}
d=json.loads(M.read_text(encoding="utf-8"))
assert d["schema"]=="phil-ai-os-a1-authority-matrix"
assert d["ceo_pre_authorized_on"]=="2026-10-05"
assert d["activation_state"]=="preauthorized_pending_preconditions"
assert d["effective_autonomy_ceiling"]=="A0"
assert d["authority_effect"]=="none"
assert d["automatic_execution_enabled"] is False
assert d["production_mutation_authorized"] is False
assert REQUIRED_DENY.issubset(set(d["denied_capabilities"]))
assert all(isinstance(v,bool) for v in d["activation_preconditions"].values())
print("AO-7 bounded A1 preactivation matrix: GREEN")

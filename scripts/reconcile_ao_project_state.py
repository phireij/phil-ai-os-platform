#!/usr/bin/env python3
"""AO-1 deterministic A0 project-state reconciler.

Consumes only committed registry/evidence files. It performs no network calls
and has no mutation capability.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "ops/project-registry/project-registry.v1.json"
RUBY_READINESS = ROOT / "ops/readiness/ruby-first-party-quick-pickup-readiness.json"

def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def evidence(kind: str, ref: str, observed_at: str, freshness: str = "fresh") -> dict[str, str]:
    return {"kind": kind, "ref": ref, "observed_at": observed_at, "freshness": freshness}

def base_state(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "project_id": p["project_id"],
        "objective": p["current_objective"],
        "milestone": "AO-1 evidence reconciliation",
        "status": "unknown",
        "repository_state": {
            "repository": p["repository"],
            "ref": p["default_branch"],
            "verified_head": p["verified_head"],
            "verified_at": p["verified_at"],
        },
        "deployment_state": {"status": "unknown", "verified_at": None, "environment": None, "evidence_ref": None},
        "completed": [], "in_progress": [], "queue": [], "blockers": [],
        "approvals_required": [], "agent_activity": [], "next_actions": [],
        "evidence": [evidence("project_registry", "ops/project-registry/project-registry.v1.json", p["verified_at"])],
        "authority": {"autonomy_ceiling": "A0", "mutation_authorized": False},
    }

def reconcile(p: dict[str, Any]) -> dict[str, Any]:
    s = base_state(p)
    pid = p["project_id"]
    if pid == "phil-ai-os":
        s["status"] = "yellow"
        s["completed"] = ["AO-MVP Phase 0 architecture and registry prepared"]
        s["in_progress"] = ["AO-1 project-state reconciliation"]
        s["blockers"] = ["AO-MVP CI execution evidence not yet observed"]
        s["next_actions"] = ["Validate AO contracts in CI", "Add live read-only evidence adapters after static reconciler"]
    elif pid == "rubys-cake-delights-hq":
        q = load(RUBY_READINESS)
        s["status"] = "yellow"
        s["completed"] = ["First-party Quick Pickup route engineering foundation prepared"]
        s["in_progress"] = ["Integrate Ruby readiness into authoritative project state"]
        if not q["production_readiness"]["production_activation_ready"]:
            s["blockers"].append("Quick Pickup production activation readiness is false")
        s["approvals_required"] = ["Production publish remains separately gated"]
        s["next_actions"] = ["Reconcile eligible catalog and Quick Pickup readiness evidence"]
        s["evidence"].append(evidence("ruby_readiness", "ops/readiness/ruby-first-party-quick-pickup-readiness.json", q["date"]))
    elif pid == "kcfc-portal":
        s["status"] = "yellow"
        s["repository_state"]["ref"] = p.get("development_branch", p["default_branch"])
        s["repository_state"]["verified_head"] = p.get("verified_development_head", p["verified_head"])
        s["completed"] = ["Read-only integration baseline registered"]
        s["in_progress"] = ["Define external repository/staging observation adapter"]
        s["blockers"] = ["Live KCFC evidence refresh not implemented in AO-1 static reconciler"]
        s["next_actions"] = ["Add read-only KCFC repository/staging evidence adapter"]
    return s

def build() -> dict[str, Any]:
    registry = load(REGISTRY)
    states = [reconcile(p) for p in sorted(registry["projects"], key=lambda x: x["priority"])]
    return {
        "schema": "phil-ai-os-master-project-status",
        "version": 1,
        "authority_effect": "none",
        "autonomy_ceiling": "A0",
        "projects": states,
    }

def main() -> None:
    print(json.dumps(build(), indent=2, sort_keys=True))

if __name__ == "__main__":
    main()

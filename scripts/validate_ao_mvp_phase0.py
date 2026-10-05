#!/usr/bin/env python3
"""Fail-closed validation for AO-MVP Phase 0 static contracts."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "ops/project-registry/project-registry.v1.json"
ARCH = ROOT / "docs/AO_MVP_PHASE_0_ARCHITECTURE_2026-10-05.md"
BASELINE = ROOT / "docs/AO_MVP_PHASE_0_VERIFIED_BASELINE_2026-10-05.md"

EXPECTED_IDS = {"phil-ai-os", "rubys-cake-delights-hq", "kcfc-portal"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"AO-MVP Phase 0 validation failed: {message}")


def main() -> None:
    require(REGISTRY.is_file(), "project registry missing")
    require(ARCH.is_file(), "architecture document missing")
    require(BASELINE.is_file(), "verified baseline missing")

    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    require(data.get("schema") == "phil-ai-os-project-registry", "unexpected registry schema")
    require(data.get("version") == 1, "unexpected registry version")
    require(data.get("authority_effect") == "none", "Phase 0 must not change authority")
    require(data.get("autonomy_ceiling") == "A0", "Phase 0 must remain A0")

    projects = data.get("projects")
    require(isinstance(projects, list), "projects must be a list")
    ids = [p.get("project_id") for p in projects]
    require(len(ids) == len(set(ids)), "project_id values must be unique")
    require(set(ids) == EXPECTED_IDS, "initial project set must be exact")

    for project in projects:
        pid = project.get("project_id", "<unknown>")
        require(project.get("mutation_authorized") is False, f"{pid} must remain non-authorizing")
        require(bool(project.get("repository")), f"{pid} repository missing")
        require(bool(project.get("verified_head")), f"{pid} verified_head missing")
        require(bool(project.get("verified_at")), f"{pid} verified_at missing")
        require(bool(project.get("current_objective")), f"{pid} objective missing")

    kcfc = next(p for p in projects if p["project_id"] == "kcfc-portal")
    require(kcfc.get("role") == "external_project_read_only_integration", "KCFC must begin read-only")

    architecture = ARCH.read_text(encoding="utf-8")
    for token in ("Mission Control: read-only", "A1 is not authorized", "awaiting_ceo_approval"):
        require(token in architecture, f"architecture safety token missing: {token}")

    print("AO-MVP Phase 0 static contracts: GREEN")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fail closed on mutable GitHub Actions dependencies and risky workflow triggers."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

ACTION_SHA_RE = re.compile(r"^[^\s@]+@[0-9a-fA-F]{40}$")
DOCKER_DIGEST_RE = re.compile(r"^docker://[^\s@]+@sha256:[0-9a-fA-F]{64}$")
USES_RE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)")
PULL_REQUEST_TARGET_RE = re.compile(r"^\s*pull_request_target\s*:")
WRITE_ALL_RE = re.compile(r"^\s*permissions\s*:\s*write-all\s*(?:#.*)?$")


def workflow_files(root: Path) -> list[Path]:
    workflow_dir = root / ".github" / "workflows"
    return sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")])


def validate_workflow(path: Path) -> list[str]:
    errors: list[str] = []
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue

        if PULL_REQUEST_TARGET_RE.match(raw_line):
            errors.append(
                f"{path}:{lineno}: pull_request_target is prohibited; use pull_request with read-only permissions"
            )

        if WRITE_ALL_RE.match(raw_line):
            errors.append(f"{path}:{lineno}: permissions: write-all is prohibited")

        match = USES_RE.match(raw_line)
        if not match:
            continue

        reference = match.group(1).strip("'\"")
        if reference.startswith("./"):
            continue
        if "${{" in reference:
            errors.append(f"{path}:{lineno}: dynamic action reference is prohibited: {reference}")
            continue
        if reference.startswith("docker://"):
            if not DOCKER_DIGEST_RE.fullmatch(reference):
                errors.append(
                    f"{path}:{lineno}: Docker action must be pinned by sha256 digest: {reference}"
                )
            continue
        if not ACTION_SHA_RE.fullmatch(reference):
            errors.append(
                f"{path}:{lineno}: action must be pinned to an immutable 40-character commit SHA: {reference}"
            )

    return errors


def validate_repository(root: Path) -> list[str]:
    files = workflow_files(root)
    if not files:
        return [f"{root}: no GitHub Actions workflow files found"]

    errors: list[str] = []
    for path in files:
        errors.extend(validate_workflow(path))
    return errors


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    args = parser.parse_args(list(argv) if argv is not None else None)

    errors = validate_repository(args.root.resolve())
    if errors:
        print("PHIL_AI_OS_WORKFLOW_SUPPLY_CHAIN_POLICY_RED")
        for error in errors:
            print(f"- {error}")
        return 1

    files = workflow_files(args.root.resolve())
    print(f"validated_workflows={len(files)}")
    print("PHIL_AI_OS_WORKFLOW_SUPPLY_CHAIN_POLICY_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

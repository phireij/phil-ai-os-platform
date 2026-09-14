#!/usr/bin/env python3
"""Fail closed on mutable GitHub Actions dependencies and risky workflow triggers."""

from __future__ import annotations

import argparse
import fnmatch
import re
from pathlib import Path
from typing import Iterable

ACTION_SHA_RE = re.compile(r"^[^\s@]+@[0-9a-fA-F]{40}$")
DOCKER_DIGEST_RE = re.compile(r"^docker://[^\s@]+@sha256:[0-9a-fA-F]{64}$")
USES_RE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)")
PULL_REQUEST_TARGET_RE = re.compile(r"^\s*pull_request_target\s*:")
WRITE_ALL_RE = re.compile(r"^\s*permissions\s*:\s*write-all\s*(?:#.*)?$")

# Historical Phase 1/2 workflows predate immutable action pinning. They remain
# visible as technical debt, but any touched workflow is validated strictly by CI.
# This allowlist applies only to mutable action refs; unsafe triggers/permissions
# are never grandfathered.
LEGACY_MUTABLE_ACTION_GLOBS = (
    "phase-1-*.yml",
    "phase-2-*.yml",
    "production-prep-ruby-business-profile-ci.yml",
)


def workflow_files(root: Path) -> list[Path]:
    workflow_dir = root / ".github" / "workflows"
    return sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")])


def is_legacy_mutable_action_file(path: Path) -> bool:
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in LEGACY_MUTABLE_ACTION_GLOBS)


def validate_workflow(path: Path, *, allow_legacy_mutable_actions: bool = False) -> list[str]:
    errors: list[str] = []
    legacy_action_exemption = allow_legacy_mutable_actions and is_legacy_mutable_action_file(path)

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
            if not DOCKER_DIGEST_RE.fullmatch(reference) and not legacy_action_exemption:
                errors.append(
                    f"{path}:{lineno}: Docker action must be pinned by sha256 digest: {reference}"
                )
            continue
        if not ACTION_SHA_RE.fullmatch(reference) and not legacy_action_exemption:
            errors.append(
                f"{path}:{lineno}: action must be pinned to an immutable 40-character commit SHA: {reference}"
            )

    return errors


def selected_workflow_files(root: Path, paths_file: Path | None) -> list[Path]:
    if paths_file is None:
        return workflow_files(root)

    files: list[Path] = []
    if not paths_file.exists():
        return files
    for raw_path in paths_file.read_text(encoding="utf-8").splitlines():
        raw_path = raw_path.strip()
        if not raw_path:
            continue
        candidate = (root / raw_path).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue
        if candidate.is_file() and candidate.suffix in {".yml", ".yaml"} and candidate.parent == (root / ".github" / "workflows").resolve():
            files.append(candidate)
    return sorted(set(files))


def validate_repository(
    root: Path,
    *,
    allow_legacy_mutable_actions: bool = False,
    paths_file: Path | None = None,
) -> list[str]:
    files = selected_workflow_files(root, paths_file)
    if paths_file is None and not files:
        return [f"{root}: no GitHub Actions workflow files found"]

    errors: list[str] = []
    for path in files:
        errors.extend(
            validate_workflow(path, allow_legacy_mutable_actions=allow_legacy_mutable_actions)
        )
    return errors


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument(
        "--allow-legacy-mutable-actions",
        action="store_true",
        help="grandfather only known historical mutable action refs during the full-repository scan",
    )
    parser.add_argument(
        "--paths-file",
        type=Path,
        help="validate only workflow paths listed in this newline-delimited file; no legacy exemption is implied",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = args.root.resolve()
    errors = validate_repository(
        root,
        allow_legacy_mutable_actions=args.allow_legacy_mutable_actions,
        paths_file=args.paths_file,
    )
    if errors:
        print("PHIL_AI_OS_WORKFLOW_SUPPLY_CHAIN_POLICY_RED")
        for error in errors:
            print(f"- {error}")
        return 1

    files = selected_workflow_files(root, args.paths_file)
    print(f"validated_workflows={len(files)}")
    if args.allow_legacy_mutable_actions:
        print("legacy_mutable_action_baseline=explicitly_grandfathered_until_touched")
    print("PHIL_AI_OS_WORKFLOW_SUPPLY_CHAIN_POLICY_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

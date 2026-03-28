#!/usr/bin/env python3
"""Clean generated/runtime artifact folders (mvn-clean style)."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean generated and diagnostic artifacts.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Repository root (defaults to current project root).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be removed without deleting files.",
    )
    return parser.parse_args()


def _remove_dir(path: Path, *, dry_run: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f"skip (missing): {path}"
    if dry_run:
        return True, f"would remove dir: {path}"
    shutil.rmtree(path)
    return True, f"removed dir: {path}"


def _remove_file(path: Path, *, dry_run: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f"skip (missing): {path}"
    if dry_run:
        return True, f"would remove file: {path}"
    path.unlink()
    return True, f"removed file: {path}"


def _ensure_dir(path: Path, *, dry_run: bool) -> tuple[bool, str]:
    if path.exists():
        return False, f"keep dir: {path}"
    if dry_run:
        return True, f"would create dir: {path}"
    path.mkdir(parents=True, exist_ok=True)
    return True, f"created dir: {path}"


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()

    dir_targets = [
        repo_root / "generated",
        repo_root / "generated-artifacts",
        repo_root / "build" / "diagnostics",
        repo_root / "build" / "test-artifacts",
    ]
    file_targets = [
        repo_root / "build" / "effective-topology.json",
        repo_root / "build" / "effective-topology.yaml",
        repo_root / "build" / "plugin-execution-trace.json",
    ]

    removed = 0
    print("Cleaning generated/runtime artifacts:")
    for target in dir_targets:
        changed, message = _remove_dir(target, dry_run=args.dry_run)
        removed += int(changed)
        print(f" - {message}")
    for target in file_targets:
        changed, message = _remove_file(target, dry_run=args.dry_run)
        removed += int(changed)
        print(f" - {message}")

    recreated = 0
    scaffold_dirs = [
        repo_root / "generated",
        repo_root / "build",
    ]
    print("Ensuring required scaffold directories:")
    for target in scaffold_dirs:
        changed, message = _ensure_dir(target, dry_run=args.dry_run)
        recreated += int(changed)
        print(f" - {message}")

    if args.dry_run:
        print(f"Dry-run complete. Targets that would be cleaned: {removed}; dirs to create: {recreated}")
    else:
        print(f"Cleanup complete. Targets cleaned: {removed}; dirs created: {recreated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate repository workspace layout invariants."""

from __future__ import annotations

import argparse
from pathlib import Path

LEGACY_ROOT_DIRS = ("v4", "v5")


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate workspace layout invariants.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Repository root to validate.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    present = [name for name in LEGACY_ROOT_DIRS if (repo_root / name).exists()]
    if present:
        joined = ", ".join(present)
        print(f"Workspace layout: FAIL (legacy roots present: {joined})")
        print("Remove these directories and keep all development in repository root layout.")
        return 1

    print("Workspace layout: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

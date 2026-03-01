#!/usr/bin/env python3
"""Clean managed generated roots and known scratch leftovers."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
GENERATED_ROOT = REPO_ROOT / "generated"

MANAGED_ROOTS = [
    GENERATED_ROOT / "ansible",
    GENERATED_ROOT / "bootstrap",
    GENERATED_ROOT / "docs",
    GENERATED_ROOT / "terraform",
]

SAFE_SCRATCH_PATHS = [
    GENERATED_ROOT / ".fixture-matrix-debug",
    GENERATED_ROOT / "terraform-mikrotik",
    GENERATED_ROOT / "validation",
    GENERATED_ROOT / "tmp-answer.toml",
]


def remove_path(path: Path) -> bool:
    """Remove a file or directory when present."""
    if not path.exists():
        return False

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def clean_generated(include_scratch: bool, verbose: bool) -> int:
    """Clean canonical managed roots and optionally scratch leftovers."""
    removed: list[Path] = []

    for path in MANAGED_ROOTS:
        if remove_path(path):
            removed.append(path)

    if include_scratch:
        for path in SAFE_SCRATCH_PATHS:
            if remove_path(path):
                removed.append(path)

    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)

    if verbose:
        print("=" * 70)
        print("Generated Cleanup (ADR 0054)")
        print("=" * 70)
        print(f"Generated root: {GENERATED_ROOT}")
        print(f"Scratch cleanup: {'enabled' if include_scratch else 'disabled'}")
        print()
        if removed:
            print("Removed paths:")
            for path in removed:
                print(f"  - {path}")
        else:
            print("Nothing to remove.")
        print("=" * 70)

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean managed generated roots and known scratch leftovers")
    parser.add_argument(
        "--no-scratch",
        action="store_true",
        help="Only clean canonical managed roots; keep scratch leftovers",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress summary output",
    )
    args = parser.parse_args()

    sys.exit(clean_generated(include_scratch=not args.no_scratch, verbose=not args.quiet))


if __name__ == "__main__":
    main()

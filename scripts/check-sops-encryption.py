#!/usr/bin/env python3
"""Verify that tracked secrets YAML files are SOPS-encrypted."""

from __future__ import annotations

import re
import sys
from pathlib import Path

SOPS_MARKER_RE = re.compile(r"(?m)^\s*sops:\s*$")
SECRET_SUBDIRS = ("instances", "terraform", "ansible", "bootstrap")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    errors: list[str] = []

    for subdir in SECRET_SUBDIRS:
        directory = repo_root / "secrets" / subdir
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                errors.append(f"ERROR: failed to read {path}: {exc}")
                continue
            if not SOPS_MARKER_RE.search(content):
                errors.append(f"ERROR: {path} is not encrypted (missing top-level 'sops:' block).")

    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

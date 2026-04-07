#!/usr/bin/env python3
"""Validate repository boundary hygiene for changed files.

This gate is intentionally diff-based to avoid instantly breaking CI for
historical noise that may still be present in the repository.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_PATTERNS = (
    r"(^|/)node_modules/",
    r"(^|/)package\.json$",
    r"(^|/)package-lock\.json$",
    r"(^|/)\.coverage(\..*)?$",
    r"(^|/)[^/]+\.iml$",
    r"(^|/)[^/]+\.lnk$",
    r"(^|/)\.claude/",
    r"(^|/)\.codex/",
    r"(^|/)Заметки/",
)


def _run_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _resolve_diff_range() -> str:
    github_before = os.environ.get("GITHUB_EVENT_BEFORE", "").strip()
    github_base_ref = os.environ.get("GITHUB_BASE_REF", "").strip()

    if github_base_ref:
        base = f"origin/{github_base_ref}"
        try:
            _run_git(["rev-parse", "--verify", base])
            return f"{base}...HEAD"
        except subprocess.CalledProcessError:
            pass

    if github_before and github_before != "0000000000000000000000000000000000000000":
        try:
            _run_git(["rev-parse", "--verify", github_before])
            return f"{github_before}...HEAD"
        except subprocess.CalledProcessError:
            pass

    try:
        _run_git(["rev-parse", "--verify", "HEAD~1"])
        return "HEAD~1...HEAD"
    except subprocess.CalledProcessError:
        return "HEAD"


def _changed_files(diff_range: str) -> list[str]:
    try:
        output = _run_git(["diff", "--name-only", diff_range])
    except subprocess.CalledProcessError:
        return []
    if not output:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def main() -> int:
    diff_range = _resolve_diff_range()
    changed = _changed_files(diff_range)

    violations: list[str] = []
    compiled = [re.compile(pattern) for pattern in FORBIDDEN_PATTERNS]
    for path in changed:
        normalized = path.replace("\\", "/")
        if any(regex.search(normalized) for regex in compiled):
            violations.append(normalized)

    if not violations:
        print(f"[repo-hygiene] PASS (range={diff_range}, changed_files={len(changed)})")
        return 0

    print(f"[repo-hygiene] FAIL (range={diff_range})")
    print("Forbidden files/directories in change set:")
    for row in sorted(violations):
        print(f"  - {row}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

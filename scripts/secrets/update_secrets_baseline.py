#!/usr/bin/env python3
"""Auto-update .secrets.baseline (no BOM) before detect-secrets pre-commit hook.

Runs detect-secrets scan with the same exclude patterns as the pre-commit hook,
merges with the existing baseline to preserve is_secret annotations, writes the
result without BOM, and stages the updated baseline file.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE = REPO_ROOT / ".secrets.baseline"

EXCLUDES = [
    r"v4/.*",
    r"\.github/workflows/.*",
    r"Migrated_and_archived/.*",
    r"v5/projects/.*/secrets/.*",
    r"v5/projects/.*/project\.yaml",
    r"v5/projects/.*/framework\.lock\.yaml",
    r"v5/tests/.*",
    r"docs/.*",
    r"v5/topology/object-modules/.*/obj\..*\.yaml",
    r"v5/topology-tools/plugins/plugins\.yaml",
]


def main() -> int:
    cmd = ["detect-secrets", "scan"]
    if BASELINE.exists():
        cmd += ["--baseline", str(BASELINE)]
    for pattern in EXCLUDES:
        cmd += ["--exclude-files", pattern]

    result = subprocess.run(cmd, capture_output=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        print(
            f"[update-baseline] detect-secrets scan failed:\n{result.stderr.decode(errors='replace')}",
            file=sys.stderr,
        )
        return result.returncode

    BASELINE.write_bytes(result.stdout)

    subprocess.run(
        ["git", "add", str(BASELINE)],
        cwd=str(REPO_ROOT),
        check=False,
    )
    print("[update-baseline] .secrets.baseline updated and staged.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

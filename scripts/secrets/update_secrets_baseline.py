#!/usr/bin/env python3
"""Auto-update .secrets.baseline (no BOM) before detect-secrets pre-commit hook.

Runs detect-secrets scan with the same exclude patterns as the pre-commit hook,
merges with the existing baseline to preserve is_secret annotations, writes the
result without BOM, and stages the updated baseline file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / ".secrets.baseline"

# Keep this list aligned with the detect-secrets hook exclude list in
# `.pre-commit-config.yaml` to avoid baseline churn between the update
# step and the check step.
EXCLUDES = [
    r"v4/.*",
    r"archive/.*",
    r"\.github/workflows/.*",
    r"Migrated_and_archived/.*",
    r"manual-scripts/.*",
    r"projects/.*/secrets/.*",
    r"projects/.*/project\.yaml$",
    r"projects/.*/framework\.lock\.yaml$",
    r"tests/.*",
    r"docs/.*",
    r"topology/object-modules/.*/obj\..*\.yaml$",
    r"topology-tools/plugins/plugins\.yaml$",
    r"topology-tools/(audit-strict-runtime-entrypoints|bootstrap-project-repo|cutover-readiness-report)\.py$",
    r"ansible/group_vars/.*\.yml\.example$",
    r"ansible/.*\.sh$",
    r"ansible/README\.md$",
    r"bootstrap/.*",
    r"configs/vpn/.*",
    r"docs/guides/.*",
    r"secrets/.*\.yaml$",
    r"MIGRATION\.md$",
    r"\.secrets\.baseline$",
]


def main() -> int:
    cmd = [sys.executable, "-m", "detect_secrets", "scan"]
    using_existing_baseline = False
    if BASELINE.exists():
        try:
            json.loads(BASELINE.read_text(encoding="utf-8"))
            cmd += ["--baseline", str(BASELINE)]
            using_existing_baseline = True
        except Exception:
            print(
                "[update-baseline] Existing baseline is not valid UTF-8 JSON; regenerating from scratch.",
                file=sys.stderr,
            )
    for pattern in EXCLUDES:
        cmd += ["--exclude-files", pattern]

    result = subprocess.run(cmd, capture_output=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        print(
            f"[update-baseline] detect-secrets scan failed:\n{result.stderr.decode(errors='replace')}",
            file=sys.stderr,
        )
        return result.returncode

    # detect-secrets v1.5 updates the baseline file in-place when --baseline is provided
    # and may emit empty stdout. Older behavior emitted baseline JSON to stdout.
    if result.stdout:
        BASELINE.write_bytes(result.stdout)
    elif not (using_existing_baseline and BASELINE.exists() and BASELINE.stat().st_size > 0):
        print(
            "[update-baseline] detect-secrets scan produced empty output and no valid baseline file exists.",
            file=sys.stderr,
        )
        return 1

    subprocess.run(
        ["git", "add", str(BASELINE)],
        cwd=str(REPO_ROOT),
        check=False,
    )
    print("[update-baseline] .secrets.baseline updated and staged.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Auto-update L0 metadata.last_updated for topology changes."""

from __future__ import annotations

import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

LAST_UPDATED_RE = re.compile(r"^(\s*last_updated:\s*)(['\"]?)(\d{4}-\d{2}-\d{2})(['\"]?)\s*$", re.MULTILINE)


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=True,
    )
    return Path(result.stdout.strip()).resolve()


def _has_topology_changes(repo_root: Path) -> bool:
    staged = _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB"], repo_root)
    for raw in staged.splitlines():
        path = raw.strip().replace("\\", "/")
        if not path:
            continue
        if path == "v4/topology.yaml" or path.startswith("v4/topology/"):
            return True
    return False


def _update_last_updated(file_path: Path, today: str) -> bool:
    content = file_path.read_text(encoding="utf-8")
    match = LAST_UPDATED_RE.search(content)
    if not match:
        raise ValueError(f"Could not find metadata.last_updated in {file_path}")
    if match.group(3) == today:
        return False

    quote = match.group(2) or "'"
    replacement = f"{match.group(1)}{quote}{today}{quote}"
    updated = LAST_UPDATED_RE.sub(replacement, content, count=1)
    file_path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    repo_root = _repo_root()
    if not _has_topology_changes(repo_root):
        return 0

    l0_meta = repo_root / "v4" / "topology" / "L0-meta.yaml"
    today = dt.date.today().isoformat()
    changed = _update_last_updated(l0_meta, today)
    if not changed:
        return 0

    _run_git(["add", str(l0_meta.relative_to(repo_root))], repo_root)
    print(f"Updated v4/topology/L0-meta.yaml last_updated to {today}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr or str(exc))
        raise SystemExit(1)
    except Exception as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1)

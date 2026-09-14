"""The committed lock must describe the committed content.

`framework.lock.yaml` carries an integrity hash over everything in
`distribution.include`. If it is regenerated before the last edit of a change,
the commit ships a lock describing a tree that no longer exists - and every check
that runs with `--strict-model-lock` fails on a fresh checkout while passing in
the working tree where the lock was last refreshed.

That happened at `12f4e836`: the lock matched locally, and an isolated worktree at
that commit failed `E7824`. Nothing caught it, because every local run had a lock
refreshed after the edits and before the tests.

This is the guard. It runs the same verification the `framework:verify-lock` task
does, so a divergent lock fails here rather than in someone else's checkout.

**A second guard, added 2026-09-14.** The first one only proved the lock matched
*this* tree. A review established that the hash also covered five gitignored
`*.egg-info` files written by `pip install -e`, so a clean checkout computed a
different hash from an installed working tree - and the earlier explanation, a
lock refreshed before the last edit, was never established. The second test below
computes the hash over tracked files alone, which is what a fresh clone has.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFIER = REPO_ROOT / "topology-tools" / "verify-framework-lock.py"


def test_the_framework_lock_matches_the_tree_it_describes() -> None:
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), "--strict"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, (
        "the framework lock does not describe the current tree. Regenerate it as the *last* step "
        "before committing - a lock refreshed before the final edit ships a description of a tree "
        "that no longer exists, and only fails on a fresh checkout.\n"
        f"{completed.stdout}{completed.stderr}"
    )


def test_the_hash_covers_only_files_a_fresh_clone_would_have() -> None:
    """Every file inside the distribution must be tracked by git.

    An untracked file inside the hash makes the lock unreproducible: the machine
    that generated it agrees with itself and nobody else does. Installation
    metadata is the case that actually occurred - five `*.egg-info` files written
    by `pip install -e` - and this refuses the class rather than that instance.

    The walk is repeated here rather than taken from `collect_framework_files`,
    which reports distribution *target* paths. What matters for reproducibility is
    which source files were read.
    """
    sys.path.insert(0, str(REPO_ROOT / "topology-tools"))
    import yaml  # noqa: PLC0415

    from framework_lock import _excluded, _parse_distribution_includes  # noqa: PLC0415

    manifest = yaml.safe_load((REPO_ROOT / "topology" / "framework.yaml").read_text(encoding="utf-8"))
    distribution = manifest["distribution"]
    excludes = [str(item) for item in distribution.get("exclude_globs", [])]

    tracked = set(
        subprocess.run(
            ["git", "ls-files"], cwd=REPO_ROOT, text=True, capture_output=True, check=True
        ).stdout.splitlines()
    )

    read: list[str] = []
    for include_source, _ in _parse_distribution_includes(distribution["include"]):
        candidate = (REPO_ROOT / include_source).resolve()
        paths = [candidate] if candidate.is_file() else [item for item in candidate.rglob("*") if item.is_file()]
        for path in paths:
            relative = path.relative_to(REPO_ROOT).as_posix()
            if not _excluded(relative, excludes):
                read.append(relative)

    assert read, "the distribution walk found nothing; this test would prove nothing"
    untracked = sorted(set(read) - tracked)

    assert not untracked, (
        "these files are inside the framework integrity hash and are not in git, so a clean "
        f"checkout cannot reproduce the lock: {untracked}"
    )

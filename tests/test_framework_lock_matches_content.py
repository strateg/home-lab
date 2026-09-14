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

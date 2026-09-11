#!/usr/bin/env python3
"""Obsolete detection must not see this run's own sibling output (W13).

A generator marks an existing file it no longer plans to write as obsolete. While
that check scanned the output root live, it also saw files that sibling
generators had just written during the same run, so the result depended on
scheduling: five generations of identical sources gave the orangepi bootstrap
plan four different obsolete lists, and the entries named the mikrotik and
proxmox generators' fresh output.

That was not only unstable. With `artifact_obsolete_action` set to `delete`
instead of the default `warn`, one generator would have deleted another's output.

The orchestrator now takes the inventory before any stage runs, which is what
obsolete is supposed to mean, and generators consume it.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "topology-tools"))

from compiler_plugin_context import _pre_run_artifact_inventory
from plugins.generators.artifact_contract import _existing_paths_for_obsolete_check


class _Ctx:
    def __init__(self, config: dict) -> None:
        self.config = config


def test_inventory_is_preferred_over_a_live_scan(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    (root / "sub").mkdir(parents=True)
    before = root / "sub" / "from-previous-run.txt"
    before.write_text("x", encoding="utf-8")
    inventory = _pre_run_artifact_inventory(root)

    # A sibling writes during the run; the live directory now holds both files.
    sibling = root / "sub" / "written-by-a-sibling.txt"
    sibling.write_text("y", encoding="utf-8")

    seen = _existing_paths_for_obsolete_check(ctx=_Ctx({"artifact_pre_run_inventory": inventory}), output_root=root)

    assert str(before.resolve()) in seen
    assert str(sibling.resolve()) not in seen, "a sibling's fresh output is not an obsolete leftover"


def test_inventory_is_scoped_to_the_requested_root(tmp_path: Path) -> None:
    root = tmp_path / "generated"
    other = tmp_path / "elsewhere"
    (root / "a").mkdir(parents=True)
    other.mkdir()
    mine = root / "a" / "mine.txt"
    mine.write_text("x", encoding="utf-8")
    (other / "theirs.txt").write_text("y", encoding="utf-8")

    inventory = _pre_run_artifact_inventory(root) + _pre_run_artifact_inventory(other)
    seen = _existing_paths_for_obsolete_check(ctx=_Ctx({"artifact_pre_run_inventory": inventory}), output_root=root)

    assert seen == {str(mine.resolve())}


def test_live_scan_remains_the_fallback_without_an_inventory(tmp_path: Path) -> None:
    """A generator driven outside the orchestrator still works."""
    root = tmp_path / "generated"
    root.mkdir()
    present = root / "present.txt"
    present.write_text("x", encoding="utf-8")

    seen = _existing_paths_for_obsolete_check(ctx=_Ctx({}), output_root=root)

    assert seen == {str(present.resolve())}


def test_absent_root_yields_an_empty_inventory(tmp_path: Path) -> None:
    assert _pre_run_artifact_inventory(tmp_path / "never-created") == []

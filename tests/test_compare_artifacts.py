#!/usr/bin/env python3
"""Checks for the artifact comparison tool (W13).

The tool exists because the obvious comparison is invalid: generated output is
gitignored, so `git status` reports nothing about it whatever the artifacts do.
These tests pin what it excludes and, more importantly, what it must not.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "validation"))

from compare_artifacts import NON_SEMANTIC_FILES, compare


def _tree(root: Path, files: dict[str, str]) -> Path:
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def test_identical_trees_report_parity(tmp_path: Path) -> None:
    files = {"a/one.tf": "resource {}\n", "b/two.json": "{}\n"}
    report = compare(_tree(tmp_path / "l", files), _tree(tmp_path / "r", files))

    assert report["changed"] == []
    assert report["added"] == []
    assert report["removed"] == []
    assert report["files_compared"] == 2


def test_content_difference_is_reported(tmp_path: Path) -> None:
    left = _tree(tmp_path / "l", {"a/one.tf": 'comment = "VPN Tunnel Zone"\n'})
    right = _tree(tmp_path / "r", {"a/one.tf": 'comment = "VPN Exit Zone"\n'})

    report = compare(left, right)

    assert report["changed"] == ["a/one.tf"]


def test_added_and_removed_files_are_reported_separately(tmp_path: Path) -> None:
    left = _tree(tmp_path / "l", {"keep.tf": "x\n", "gone.tf": "y\n"})
    right = _tree(tmp_path / "r", {"keep.tf": "x\n", "new.tf": "z\n"})

    report = compare(left, right)

    assert report["removed"] == ["gone.tf"]
    assert report["added"] == ["new.tf"]
    assert report["changed"] == []


def test_declared_non_semantic_file_is_excluded_with_its_reason(tmp_path: Path) -> None:
    name = next(iter(NON_SEMANTIC_FILES))
    left = _tree(tmp_path / "l", {name: '{"generated_at": "1"}\n'})
    right = _tree(tmp_path / "r", {name: '{"generated_at": "2"}\n'})

    report = compare(left, right)

    assert report["changed"] == []
    assert name in report["excluded_as_non_semantic"]
    assert report["excluded_as_non_semantic"][name], "an exclusion must carry its justification"


def test_known_unstable_plans_are_reported_rather_than_excluded() -> None:
    """W13's ordering defect must stay visible.

    The artifact-plan files vary between parallel runs because obsolete detection
    scans the live output directory while sibling generators write into it.
    Excluding them would hide the defect instead of fixing it.
    """
    for name in NON_SEMANTIC_FILES:
        assert ".state/artifact-plans" not in name, f"{name} must not be excluded; it is a defect to fix"

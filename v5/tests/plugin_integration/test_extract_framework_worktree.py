#!/usr/bin/env python3
"""Tests for extract-framework-worktree utility."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "v5" / "topology-tools" / "extract-framework-worktree.py"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_fake_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "v5" / "topology" / "framework.yaml", "schema_version: 1\nframework_id: test\n")
    _write(root / "v5" / "topology" / "layer-contract.yaml", "schema_version: 1\n")
    _write(root / "v5" / "topology" / "model.lock.yaml", "schema_version: 1\n")
    _write(root / "v5" / "topology" / "profile-map.yaml", "schema_version: 1\n")
    _write(root / "v5" / "topology" / "class-modules" / "router" / "class.router.test.yaml", "class: test\n")
    _write(root / "v5" / "topology" / "object-modules" / "router" / "obj.router.test.yaml", "object: test\n")
    _write(root / "v5" / "topology-tools" / "compile-topology.py", "# test\n")
    _write(root / "v5" / "tests" / "plugin_api" / "test_api.py", "def test_ok():\n    assert True\n")
    _write(root / "v5" / "tests" / "plugin_contract" / "test_contract.py", "def test_ok():\n    assert True\n")
    _write(root / "v5" / "tests" / "plugin_integration" / "test_integration.py", "def test_ok():\n    assert True\n")
    _write(root / "v5" / "tests" / "plugin_regression" / "test_regression.py", "def test_ok():\n    assert True\n")
    _write(root / "v5" / "tests" / "conftest.py", "# test\n")
    return root


def test_extract_worktree_without_tests(tmp_path: Path) -> None:
    repo_root = _make_fake_repo(tmp_path)
    output_root = tmp_path / "extract"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo_root),
            "--output-root",
            str(output_root),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert (output_root / "framework.yaml").exists()
    assert (output_root / "class-modules").exists()
    assert (output_root / "object-modules").exists()
    assert (output_root / "topology-tools").exists()
    assert (output_root / "tests").exists() is False
    manifest = yaml.safe_load((output_root / "extraction-manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["include_tests"] is False


def test_extract_worktree_with_tests(tmp_path: Path) -> None:
    repo_root = _make_fake_repo(tmp_path)
    output_root = tmp_path / "extract"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo_root),
            "--output-root",
            str(output_root),
            "--include-tests",
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert (output_root / "tests" / "plugin_api" / "test_api.py").exists()
    assert (output_root / "tests" / "plugin_integration" / "test_integration.py").exists()
    manifest = yaml.safe_load((output_root / "extraction-manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["include_tests"] is True

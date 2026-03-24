#!/usr/bin/env python3
"""Tests for bootstrap-framework-repo utility."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "topology-tools" / "bootstrap-framework-repo.py"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fake_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "topology" / "framework.yaml", "schema_version: 1\nframework_id: test\n")
    _write(root / "topology" / "layer-contract.yaml", "schema_version: 1\n")
    _write(root / "topology" / "model.lock.yaml", "schema_version: 1\n")
    _write(root / "topology" / "profile-map.yaml", "schema_version: 1\n")
    _write(root / "topology" / "class-modules" / "router" / "class.router.test.yaml", "class: test\n")
    _write(root / "topology" / "object-modules" / "router" / "obj.router.test.yaml", "object: test\n")
    _write(root / "topology-tools" / "compile-topology.py", "# test\n")
    _write(root / "tests" / "plugin_api" / "test_api.py", "def test_ok():\n    assert True\n")
    _write(root / "tests" / "plugin_contract" / "test_contract.py", "def test_ok():\n    assert True\n")
    _write(root / "tests" / "plugin_integration" / "test_integration.py", "def test_ok():\n    assert True\n")
    _write(root / "tests" / "plugin_regression" / "test_regression.py", "def test_ok():\n    assert True\n")
    _write(root / "tests" / "conftest.py", "# test\n")
    _write(root / "docs" / "framework" / "templates" / "framework-release.yml", "name: test-release\n")
    subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, text=True, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=root, text=True, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, text=True, capture_output=True, check=True)
    return root


def test_bootstrap_framework_repo_outputs_expected_layout(tmp_path: Path) -> None:
    source_root = _fake_repo(tmp_path)
    output_root = tmp_path / "framework-repo"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(source_root),
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
    assert (output_root / "framework.yaml").exists()
    assert (output_root / "topology" / "class-modules").exists()
    assert (output_root / "topology-tools").exists()
    assert (output_root / "tests" / "plugin_api" / "test_api.py").exists()
    assert (output_root / ".github" / "workflows" / "release.yml").exists()
    assert (output_root / "BOOTSTRAP-NOTES.md").exists()


def test_bootstrap_framework_repo_preserve_history_mode(tmp_path: Path) -> None:
    source_root = _fake_repo(tmp_path)
    output_root = tmp_path / "framework-repo-history"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(source_root),
            "--output-root",
            str(output_root),
            "--include-tests",
            "--preserve-history",
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert (output_root / ".git").exists()
    assert (output_root / "framework.yaml").exists()

    commits = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=output_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert commits.returncode == 0, commits.stdout + "\n" + commits.stderr
    assert int((commits.stdout or "0").strip()) >= 2

    notes = (output_root / "BOOTSTRAP-NOTES.md").read_text(encoding="utf-8")
    assert "preserve_history: True" in notes

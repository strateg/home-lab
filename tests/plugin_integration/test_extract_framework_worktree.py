#!/usr/bin/env python3
"""Tests for extract-framework-worktree utility."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


def _detect_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        if (candidate / "topology-tools").is_dir() or (candidate / "topology-tools").is_dir():
            return candidate
    return current.parents[3]


def _tools_root(repo_root: Path) -> Path:
    extracted = repo_root / "topology-tools"
    if extracted.is_dir():
        return extracted
    return repo_root / "topology-tools"


REPO_ROOT = _detect_repo_root()
SCRIPT = _tools_root(REPO_ROOT) / "extract-framework-worktree.py"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_fake_repo(tmp_path: Path, *, include_conftest: bool = True) -> Path:
    root = tmp_path / "repo"
    _write(
        root / "topology" / "framework.yaml",
        yaml.safe_dump(
            {
                "schema_version": 1,
                "framework_id": "test",
                "framework_api_version": "5.0.0",
                "supported_project_schema_range": ">=1.0.0 <2.0.0",
                "distribution": {
                    "layout_version": 1,
                    "include": [
                        {"from": "topology/framework.yaml", "to": "framework.yaml"},
                        {"from": "topology/class-modules", "to": "topology/class-modules"},
                        {"from": "topology/object-modules", "to": "topology/object-modules"},
                        {"from": "topology/layer-contract.yaml", "to": "topology/layer-contract.yaml"},
                        {"from": "topology/model.lock.yaml", "to": "topology/model.lock.yaml"},
                        {"from": "topology/profile-map.yaml", "to": "topology/profile-map.yaml"},
                        {"from": "topology-tools", "to": "topology-tools"},
                    ],
                },
            },
            sort_keys=False,
        ),
    )
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
    if include_conftest:
        _write(root / "tests" / "conftest.py", "# test\n")
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
    assert (output_root / "topology" / "class-modules").exists()
    assert (output_root / "topology" / "object-modules").exists()
    assert (output_root / "topology-tools").exists()
    assert (output_root / "tests").exists() is False
    manifest = yaml.safe_load((output_root / "extraction-manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["include_tests"] is False
    extracted_manifest = yaml.safe_load((output_root / "framework.yaml").read_text(encoding="utf-8"))
    include = extracted_manifest["distribution"]["include"]
    assert "framework.yaml" in include
    assert "topology/class-modules" in include
    assert "topology-tools" in include
    assert all(not str(item).startswith("v5/") for item in include)


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


def test_extract_worktree_with_tests_without_conftest(tmp_path: Path) -> None:
    repo_root = _make_fake_repo(tmp_path, include_conftest=False)
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
    assert (output_root / "tests" / "conftest.py").exists() is False

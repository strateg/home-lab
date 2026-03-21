#!/usr/bin/env python3
"""Tests for history-preserving framework extraction utility."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


def _detect_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        if (candidate / "topology-tools").is_dir() or (candidate / "v5" / "topology-tools").is_dir():
            return candidate
    return current.parents[3]


def _tools_root(repo_root: Path) -> Path:
    extracted = repo_root / "topology-tools"
    if extracted.is_dir():
        return extracted
    return repo_root / "v5" / "topology-tools"


REPO_ROOT = _detect_repo_root()
SCRIPT = _tools_root(REPO_ROOT) / "extract-framework-history.py"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=path, text=True, capture_output=True, check=False)


def _init_fixture_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(
        root / "v5" / "topology" / "framework.yaml",
        yaml.safe_dump(
            {
                "schema_version": 1,
                "framework_id": "home-lab-v5-framework",
                "framework_api_version": "5.0.0",
                "supported_project_schema_range": ">=1.0.0 <2.0.0",
                "distribution": {
                    "layout_version": 1,
                    "include": [
                        {"from": "v5/topology/framework.yaml", "to": "framework.yaml"},
                        {"from": "v5/topology/class-modules", "to": "topology/class-modules"},
                        {"from": "v5/topology/object-modules", "to": "topology/object-modules"},
                        {"from": "v5/topology/layer-contract.yaml", "to": "topology/layer-contract.yaml"},
                        {"from": "v5/topology/model.lock.yaml", "to": "topology/model.lock.yaml"},
                        {"from": "v5/topology/profile-map.yaml", "to": "topology/profile-map.yaml"},
                        {"from": "v5/topology-tools", "to": "topology-tools"},
                    ],
                },
            },
            sort_keys=False,
        ),
    )
    _write(root / "v5" / "topology" / "layer-contract.yaml", "schema_version: 1\n")
    _write(root / "v5" / "topology" / "model.lock.yaml", "schema_version: 1\n")
    _write(root / "v5" / "topology" / "profile-map.yaml", "schema_version: 1\n")
    _write(root / "v5" / "topology" / "class-modules" / "router" / "class.router.test.yaml", "class: test\n")
    _write(root / "v5" / "topology" / "object-modules" / "router" / "obj.router.test.yaml", "object: test\n")
    _write(root / "v5" / "topology-tools" / "compile-topology.py", "# tool\n")
    _write(root / "v5" / "tests" / "plugin_api" / "test_api.py", "def test_ok():\n    assert True\n")

    assert _git(root, "init").returncode == 0
    assert _git(root, "config", "user.name", "Test User").returncode == 0
    assert _git(root, "config", "user.email", "test@example.com").returncode == 0
    assert _git(root, "add", ".").returncode == 0
    assert _git(root, "commit", "-m", "initial fixture").returncode == 0

    _write(root / "v5" / "topology" / "class-modules" / "router" / "class.router.test.yaml", "class: test-v2\n")
    assert _git(root, "add", ".").returncode == 0
    assert _git(root, "commit", "-m", "update class module").returncode == 0
    return root


def test_extract_framework_history_preserves_git_and_normalizes_layout(tmp_path: Path) -> None:
    source_root = _init_fixture_repo(tmp_path)
    output_root = tmp_path / "framework-history"
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
    assert (output_root / ".git").exists()
    assert (output_root / "framework.yaml").exists()
    assert (output_root / "topology" / "class-modules").exists()
    assert (output_root / "topology-tools").exists()
    assert (output_root / "tests" / "plugin_api" / "test_api.py").exists()

    manifest = yaml.safe_load((output_root / "framework.yaml").read_text(encoding="utf-8"))
    include = manifest["distribution"]["include"]
    assert "framework.yaml" in include
    assert all(not str(item).startswith("v5/") for item in include)

    commits = _git(output_root, "rev-list", "--count", "HEAD")
    assert commits.returncode == 0
    assert int((commits.stdout or "0").strip()) >= 2

    head = _git(output_root, "log", "-1", "--pretty=%s")
    assert head.returncode == 0
    assert "normalize extracted framework layout" in (head.stdout or "")

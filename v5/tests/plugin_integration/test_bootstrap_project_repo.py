#!/usr/bin/env python3
"""Tests for bootstrap-project-repo utility."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "v5" / "topology-tools" / "bootstrap-project-repo.py"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fake_framework_repo(tmp_path: Path) -> Path:
    root = tmp_path / "framework"
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
                        "v5/topology/framework.yaml",
                    ],
                },
            },
            sort_keys=False,
        ),
    )
    return root


def test_bootstrap_project_repo_generates_manifests_and_lock(tmp_path: Path) -> None:
    framework_root = _fake_framework_repo(tmp_path)
    output_root = tmp_path / "project"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--framework-root",
            str(framework_root),
            "--output-root",
            str(output_root),
            "--project-id",
            "home-lab",
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert (output_root / "topology.yaml").exists()
    assert (output_root / "project.yaml").exists()
    assert (output_root / "framework.lock.yaml").exists()
    assert (output_root / "instances").exists()
    assert (output_root / "secrets").exists()
    assert (output_root / "BOOTSTRAP-NOTES.md").exists()

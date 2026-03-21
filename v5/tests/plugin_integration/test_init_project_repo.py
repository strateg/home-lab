#!/usr/bin/env python3
"""Integration tests for init-project-repo utility."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "v5" / "topology-tools" / "init-project-repo.py"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=path, text=True, capture_output=True, check=False)


def _git_init_and_commit(path: Path) -> None:
    assert _git(path, "init").returncode == 0
    assert _git(path, "config", "user.name", "Test User").returncode == 0
    assert _git(path, "config", "user.email", "test@example.com").returncode == 0
    assert _git(path, "add", ".").returncode == 0
    assert _git(path, "commit", "-m", "fixture").returncode == 0


def _fake_extracted_framework_repo(tmp_path: Path) -> Path:
    root = tmp_path / "framework-extracted"
    _write(
        root / "framework.yaml",
        yaml.safe_dump(
            {
                "schema_version": 1,
                "framework_id": "infra-topology-framework",
                "framework_api_version": "1.0.0",
                "supported_project_schema_range": ">=1.0.0 <2.0.0",
                "distribution": {
                    "layout_version": 1,
                    "include": [
                        "framework.yaml",
                        "layer-contract.yaml",
                        "class-modules",
                        "object-modules",
                    ],
                },
            },
            sort_keys=False,
        ),
    )
    _write(
        root / "layer-contract.yaml",
        yaml.safe_dump(
            {
                "schema_version": 1,
                "group_layers": {
                    "meta": "L0",
                    "devices": "L1",
                    "network": "L2",
                    "storage": "L3",
                    "platform": "L4",
                    "service": "L5",
                    "monitoring": "L6",
                    "operations": "L7",
                },
            },
            sort_keys=False,
        ),
    )
    _write(root / "class-modules" / ".gitkeep", "")
    _write(root / "object-modules" / ".gitkeep", "")
    return root


def test_init_project_repo_creates_l0_l7_structure_and_submodule(tmp_path: Path) -> None:
    framework_root = _fake_extracted_framework_repo(tmp_path)
    _git_init_and_commit(framework_root)
    output_root = tmp_path / "project"

    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-root",
            str(output_root),
            "--project-id",
            "home-lab",
            "--framework-submodule-url",
            str(framework_root),
            "--skip-compile-check",
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert (output_root / ".gitmodules").exists()
    assert (output_root / "framework" / "framework.yaml").exists()
    assert (output_root / "topology.yaml").exists()
    assert (output_root / "project.yaml").exists()
    assert (output_root / "framework.lock.yaml").exists()

    for bucket in (
        "L0-meta",
        "L1-foundation",
        "L2-network",
        "L3-data",
        "L4-platform",
        "L5-application",
        "L6-observability",
        "L7-operations",
    ):
        assert (output_root / "instances" / bucket).exists()

    assert (output_root / "instances" / "L1-foundation" / "firmware" / "inst.firmware.apc.backups.650va.yaml").exists()
    assert (output_root / "instances" / "L1-foundation" / "power" / "ups-main.yaml").exists()


def test_init_project_repo_default_flow_passes_strict_compile_with_real_framework(tmp_path: Path) -> None:
    output_root = tmp_path / "project-compile"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-root",
            str(output_root),
            "--project-id",
            "home-lab",
            "--framework-submodule-url",
            str(REPO_ROOT),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert (output_root / "generated" / "effective-topology.json").exists()
    assert (output_root / "generated" / "diagnostics.json").exists()

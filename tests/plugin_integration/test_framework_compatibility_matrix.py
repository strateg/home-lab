#!/usr/bin/env python3
"""Integration tests for framework compatibility matrix utility."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATE_SCRIPT = REPO_ROOT / "topology-tools" / "generate-framework-lock.py"
MATRIX_SCRIPT = REPO_ROOT / "topology-tools" / "validate-framework-compatibility-matrix.py"


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _create_fixture_repo(tmp_path: Path, *, min_framework_version: str = "5.0.0") -> tuple[Path, Path, Path]:
    repo_root = tmp_path / "repo"
    framework_manifest = repo_root / "topology" / "framework.yaml"
    topology_manifest = repo_root / "topology" / "topology.yaml"
    project_manifest = repo_root / "projects" / "home-lab" / "project.yaml"

    _write_yaml(
        framework_manifest,
        {
            "schema_version": 1,
            "framework_id": "home-lab-v5-framework",
            "framework_api_version": "5.0.0",
            "supported_project_schema_range": ">=1.0.0 <2.0.0",
            "distribution": {
                "layout_version": 1,
                "include": [
                    "topology/framework.yaml",
                    "topology/topology.yaml",
                ],
            },
        },
    )
    _write_yaml(
        topology_manifest,
        {
            "version": "5.0.0",
            "model": "class-object-instance",
            "framework": {
                "class_modules_root": "topology/class-modules",
                "object_modules_root": "topology/object-modules",
                "model_lock": "topology/model.lock.yaml",
                "profile_map": "topology/profile-map.yaml",
                "layer_contract": "topology/layer-contract.yaml",
                "capability_catalog": "topology/class-modules/router/capability-catalog.yaml",
                "capability_packs": "topology/class-modules/router/capability-packs.yaml",
            },
            "project": {
                "active": "home-lab",
                "projects_root": "projects",
            },
        },
    )
    _write_yaml(
        project_manifest,
        {
            "schema_version": 1,
            "project_schema_version": "1.0.0",
            "project": "home-lab",
            "project_min_framework_version": min_framework_version,
            "project_contract_revision": 1,
            "instances_root": "instances",
            "secrets_root": "secrets",
        },
    )
    return repo_root, topology_manifest, project_manifest


def test_compatibility_matrix_success(tmp_path: Path) -> None:
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generated = subprocess.run(
        [
            sys.executable,
            str(GENERATE_SCRIPT),
            "--repo-root",
            str(repo_root),
            "--topology",
            str(topology_manifest),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stdout + "\n" + generated.stderr

    matrix = subprocess.run(
        [
            sys.executable,
            str(MATRIX_SCRIPT),
            "--repo-root",
            str(repo_root),
            "--topology",
            str(topology_manifest),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert matrix.returncode == 0, matrix.stdout + "\n" + matrix.stderr
    assert "Compatibility matrix: OK" in matrix.stdout


def test_compatibility_matrix_fails_when_baseline_invalid(tmp_path: Path) -> None:
    repo_root, topology_manifest, project_manifest = _create_fixture_repo(tmp_path, min_framework_version="9.0.0")
    generated = subprocess.run(
        [
            sys.executable,
            str(GENERATE_SCRIPT),
            "--repo-root",
            str(repo_root),
            "--topology",
            str(topology_manifest),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stdout + "\n" + generated.stderr

    payload = yaml.safe_load(project_manifest.read_text(encoding="utf-8"))
    payload["project_min_framework_version"] = "9.0.0"
    project_manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    matrix = subprocess.run(
        [
            sys.executable,
            str(MATRIX_SCRIPT),
            "--repo-root",
            str(repo_root),
            "--topology",
            str(topology_manifest),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert matrix.returncode != 0
    assert "baseline_ok: FAIL" in matrix.stdout

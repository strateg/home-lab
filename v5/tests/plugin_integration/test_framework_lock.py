#!/usr/bin/env python3
"""Tests for framework lock generation and verification utilities."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATE_SCRIPT = REPO_ROOT / "v5" / "topology-tools" / "generate-framework-lock.py"
VERIFY_SCRIPT = REPO_ROOT / "v5" / "topology-tools" / "verify-framework-lock.py"


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _git_init_and_commit(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, text=True, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, text=True, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        text=True,
        capture_output=True,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=path, text=True, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=path, text=True, capture_output=True, check=True)


def _create_fixture_repo(tmp_path: Path, *, min_framework_version: str = "5.0.0") -> tuple[Path, Path, Path]:
    repo_root = tmp_path / "repo"
    framework_manifest = repo_root / "v5" / "topology" / "framework.yaml"
    topology_manifest = repo_root / "v5" / "topology" / "topology.yaml"
    project_manifest = repo_root / "v5" / "projects" / "home-lab" / "project.yaml"

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
                    "v5/topology/framework.yaml",
                    "v5/topology/topology.yaml",
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
                "class_modules_root": "v5/topology/class-modules",
                "object_modules_root": "v5/topology/object-modules",
                "model_lock": "v5/topology/model.lock.yaml",
                "profile_map": "v5/topology/profile-map.yaml",
                "layer_contract": "v5/topology/layer-contract.yaml",
                "capability_catalog": "v5/topology/class-modules/router/capability-catalog.yaml",
                "capability_packs": "v5/topology/class-modules/router/capability-packs.yaml",
            },
            "project": {
                "active": "home-lab",
                "projects_root": "v5/projects",
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


def test_generate_and_verify_framework_lock_success(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generate = subprocess.run(
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
    assert generate.returncode == 0, generate.stderr

    verify = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            "--repo-root",
            str(repo_root),
            "--topology",
            str(topology_manifest),
            "--strict",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode == 0, verify.stdout + "\n" + verify.stderr
    assert "OK" in verify.stdout


def test_verify_detects_integrity_mismatch(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generate = subprocess.run(
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
    assert generate.returncode == 0, generate.stderr

    framework_manifest = repo_root / "v5" / "topology" / "framework.yaml"
    payload = yaml.safe_load(framework_manifest.read_text(encoding="utf-8"))
    payload["framework_release_channel"] = "tampered"
    framework_manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            "--repo-root",
            str(repo_root),
            "--topology",
            str(topology_manifest),
            "--strict",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode != 0
    assert "E7824" in verify.stdout


def test_verify_detects_framework_version_too_old(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path, min_framework_version="6.0.0")
    generate = subprocess.run(
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
    assert generate.returncode == 0, generate.stderr

    verify = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            "--repo-root",
            str(repo_root),
            "--topology",
            str(topology_manifest),
            "--strict",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode != 0
    assert "E7811" in verify.stdout


def test_verify_detects_missing_package_attestations(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    generate = subprocess.run(
        [
            sys.executable,
            str(GENERATE_SCRIPT),
            "--repo-root",
            str(repo_root),
            "--topology",
            str(topology_manifest),
            "--source",
            "package",
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generate.returncode == 0, generate.stderr

    lock_path = repo_root / "v5" / "projects" / "home-lab" / "framework.lock.yaml"
    payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    payload["framework"].pop("signature", None)
    payload.pop("provenance", None)
    payload.pop("sbom", None)
    lock_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            "--repo-root",
            str(repo_root),
            "--topology",
            str(topology_manifest),
            "--strict",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode != 0
    assert "E7825" in verify.stdout
    assert "E7826" in verify.stdout
    assert "E7828" in verify.stdout


def test_verify_bypasses_revision_mismatch_in_monorepo_mode(tmp_path: Path):
    repo_root, topology_manifest, _ = _create_fixture_repo(tmp_path)
    _git_init_and_commit(repo_root)

    generate = subprocess.run(
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
    assert generate.returncode == 0, generate.stderr

    lock_path = repo_root / "v5" / "projects" / "home-lab" / "framework.lock.yaml"
    payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    payload["framework"]["revision"] = "deadbeef"
    lock_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            "--repo-root",
            str(repo_root),
            "--topology",
            str(topology_manifest),
            "--strict",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode == 0, verify.stdout + "\n" + verify.stderr
    assert "E7823" not in verify.stdout


def test_verify_detects_revision_mismatch_when_framework_is_external_repo(tmp_path: Path):
    framework_root = tmp_path / "framework-repo"
    project_root = tmp_path / "project-repo"
    framework_manifest = framework_root / "v5" / "topology" / "framework.yaml"
    project_manifest = project_root / "project.yaml"
    lock_path = project_root / "framework.lock.yaml"

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
                    "v5/topology/framework.yaml",
                ],
            },
        },
    )
    _write_yaml(
        project_manifest,
        {
            "schema_version": 1,
            "project_schema_version": "1.0.0",
            "project": "home-lab",
            "project_min_framework_version": "5.0.0",
            "project_contract_revision": 1,
            "instances_root": "instances",
            "secrets_root": "secrets",
        },
    )
    _git_init_and_commit(framework_root)

    generate = subprocess.run(
        [
            sys.executable,
            str(GENERATE_SCRIPT),
            "--repo-root",
            str(project_root),
            "--topology",
            str(project_root / "missing-topology.yaml"),
            "--project-root",
            str(project_root),
            "--project-manifest",
            str(project_manifest),
            "--framework-root",
            str(framework_root),
            "--framework-manifest",
            str(framework_manifest),
            "--lock-file",
            str(lock_path),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generate.returncode == 0, generate.stderr

    payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    payload["framework"]["revision"] = "cafebabe"
    lock_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    verify = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            "--repo-root",
            str(project_root),
            "--topology",
            str(project_root / "missing-topology.yaml"),
            "--project-root",
            str(project_root),
            "--project-manifest",
            str(project_manifest),
            "--framework-root",
            str(framework_root),
            "--framework-manifest",
            str(framework_manifest),
            "--lock-file",
            str(lock_path),
            "--strict",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode != 0
    assert "E7823" in verify.stdout

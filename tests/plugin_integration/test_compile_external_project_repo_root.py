#!/usr/bin/env python3
"""Integration test for compile-topology --repo-root with external project layout."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPILE_SCRIPT = REPO_ROOT / "topology-tools" / "compile-topology.py"
GENERATE_LOCK_SCRIPT = REPO_ROOT / "topology-tools" / "generate-framework-lock.py"


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_compile_with_external_project_repo_root(tmp_path: Path) -> None:
    project_repo = tmp_path / "home-lab-project"
    framework_root = REPO_ROOT
    topology_path = project_repo / "topology.yaml"
    project_manifest = project_repo / "home-lab" / "project.yaml"
    error_catalog = project_repo / "topology-tools" / "data" / "error-catalog.yaml"
    output_json = project_repo / "generated" / "effective-topology.json"
    diagnostics_json = project_repo / "generated" / "diagnostics.json"
    diagnostics_txt = project_repo / "generated" / "diagnostics.txt"

    _write_yaml(
        topology_path,
        {
            "version": "5.0.0",
            "model": "class-object-instance",
            "framework": {
                "root": str(framework_root),
                "class_modules_root": str(framework_root / "topology" / "class-modules"),
                "object_modules_root": str(framework_root / "topology" / "object-modules"),
                "model_lock": str(framework_root / "topology" / "model.lock.yaml"),
                "profile_map": str(framework_root / "topology" / "profile-map.yaml"),
                "layer_contract": str(framework_root / "topology" / "layer-contract.yaml"),
                "capability_catalog": str(
                    framework_root / "topology" / "class-modules" / "L1-foundation" / "router" / "capability-catalog.yaml"
                ),
                "capability_packs": str(
                    framework_root / "topology" / "class-modules" / "L1-foundation" / "router" / "capability-packs.yaml"
                ),
            },
            "project": {
                "active": "home-lab",
                "projects_root": ".",
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
            "instances_root": str(REPO_ROOT / "projects" / "home-lab" / "topology" / "instances"),
            "secrets_root": str(REPO_ROOT / "projects" / "home-lab" / "secrets"),
        },
    )
    _write_yaml(error_catalog, {"version": 1, "tool": "topology-compiler", "codes": {}})

    generated = subprocess.run(
        [
            sys.executable,
            str(GENERATE_LOCK_SCRIPT),
            "--repo-root",
            str(project_repo),
            "--project-root",
            str(project_repo / "home-lab"),
            "--project-manifest",
            str(project_manifest),
            "--framework-root",
            str(framework_root),
            "--framework-manifest",
            str(framework_root / "topology" / "framework.yaml"),
            "--lock-file",
            str(project_repo / "home-lab" / "framework.lock.yaml"),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stdout + "\n" + generated.stderr

    compiled = subprocess.run(
        [
            sys.executable,
            str(COMPILE_SCRIPT),
            "--repo-root",
            str(project_repo),
            "--topology",
            str(topology_path),
            "--error-catalog",
            str(error_catalog),
            "--plugins-manifest",
            str(REPO_ROOT / "topology-tools" / "plugins" / "plugins.yaml"),
            "--secrets-mode",
            "passthrough",
            "--strict-model-lock",
            "--output-json",
            str(output_json),
            "--diagnostics-json",
            str(diagnostics_json),
            "--diagnostics-txt",
            str(diagnostics_txt),
            "--artifacts-root",
            str(project_repo / "generated-artifacts"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert compiled.returncode == 0, compiled.stdout + "\n" + compiled.stderr
    assert output_json.exists()


def test_compile_with_external_project_repo_root_uses_standalone_topology_default(tmp_path: Path) -> None:
    project_repo = tmp_path / "home-lab-project"
    framework_root = REPO_ROOT
    topology_path = project_repo / "topology.yaml"
    project_manifest = project_repo / "home-lab" / "project.yaml"
    error_catalog = project_repo / "topology-tools" / "data" / "error-catalog.yaml"
    output_json = project_repo / "generated" / "effective-topology.json"
    diagnostics_json = project_repo / "generated" / "diagnostics.json"
    diagnostics_txt = project_repo / "generated" / "diagnostics.txt"

    _write_yaml(
        topology_path,
        {
            "version": "5.0.0",
            "model": "class-object-instance",
            "framework": {
                "root": str(framework_root),
                "class_modules_root": str(framework_root / "topology" / "class-modules"),
                "object_modules_root": str(framework_root / "topology" / "object-modules"),
                "model_lock": str(framework_root / "topology" / "model.lock.yaml"),
                "profile_map": str(framework_root / "topology" / "profile-map.yaml"),
                "layer_contract": str(framework_root / "topology" / "layer-contract.yaml"),
                "capability_catalog": str(
                    framework_root / "topology" / "class-modules" / "L1-foundation" / "router" / "capability-catalog.yaml"
                ),
                "capability_packs": str(
                    framework_root / "topology" / "class-modules" / "L1-foundation" / "router" / "capability-packs.yaml"
                ),
            },
            "project": {
                "active": "home-lab",
                "projects_root": ".",
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
            "instances_root": str(REPO_ROOT / "projects" / "home-lab" / "topology" / "instances"),
            "secrets_root": str(REPO_ROOT / "projects" / "home-lab" / "secrets"),
        },
    )
    _write_yaml(error_catalog, {"version": 1, "tool": "topology-compiler", "codes": {}})

    generated = subprocess.run(
        [
            sys.executable,
            str(GENERATE_LOCK_SCRIPT),
            "--repo-root",
            str(project_repo),
            "--project-root",
            str(project_repo / "home-lab"),
            "--project-manifest",
            str(project_manifest),
            "--framework-root",
            str(framework_root),
            "--framework-manifest",
            str(framework_root / "topology" / "framework.yaml"),
            "--lock-file",
            str(project_repo / "home-lab" / "framework.lock.yaml"),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stdout + "\n" + generated.stderr

    compiled = subprocess.run(
        [
            sys.executable,
            str(COMPILE_SCRIPT),
            "--repo-root",
            str(project_repo),
            "--error-catalog",
            str(error_catalog),
            "--plugins-manifest",
            str(REPO_ROOT / "topology-tools" / "plugins" / "plugins.yaml"),
            "--secrets-mode",
            "passthrough",
            "--strict-model-lock",
            "--output-json",
            str(output_json),
            "--diagnostics-json",
            str(diagnostics_json),
            "--diagnostics-txt",
            str(diagnostics_txt),
            "--artifacts-root",
            str(project_repo / "generated-artifacts"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert compiled.returncode == 0, compiled.stdout + "\n" + compiled.stderr
    assert output_json.exists()

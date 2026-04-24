#!/usr/bin/env python3
"""Tests for bootstrap-project-repo utility."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "topology-tools" / "utils" / "bootstrap-project-repo.py"


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


def _fake_framework_repo(tmp_path: Path) -> Path:
    root = tmp_path / "framework"
    _write(
        root / "topology" / "framework.yaml",
        yaml.safe_dump(
            {
                "schema_version": 1,
                "framework_id": "home-lab-v5-framework",
                "framework_api_version": "5.0.0",
                "supported_project_schema_range": ">=1.0.0 <2.0.0",
                "distribution": {
                    "layout_version": 1,
                    "include": [
                        "topology/framework.yaml",
                    ],
                },
            },
            sort_keys=False,
        ),
    )
    _write(root / "topology" / "product-bundles" / "default.yaml", "schema_version: 1\n")
    _write(root / "topology" / "product-profiles" / "default.yaml", "schema_version: 1\n")
    return root


def _fake_extracted_framework_repo(tmp_path: Path) -> Path:
    root = tmp_path / "framework-extracted"
    _write(
        root / "framework.yaml",
        yaml.safe_dump(
            {
                "schema_version": 1,
                "framework_id": "home-lab-v5-framework",
                "framework_api_version": "5.0.0",
                "supported_project_schema_range": ">=1.0.0 <2.0.0",
                "distribution": {
                    "layout_version": 1,
                    "include": [
                        "framework.yaml",
                        "topology/class-modules",
                    ],
                },
            },
            sort_keys=False,
        ),
    )
    _write(root / "topology" / "class-modules" / "router" / "class.router.test.yaml", "class: test\n")
    _write(root / "topology" / "product-bundles" / "default.yaml", "schema_version: 1\n")
    _write(root / "topology" / "product-profiles" / "default.yaml", "schema_version: 1\n")
    return root


def _fake_seed_project_root(tmp_path: Path) -> Path:
    root = tmp_path / "seed-project"
    _write(root / "topology" / "instances" / "compute" / "vm.seed.yaml", "instance: vm.seed\n")
    _write(root / "secrets" / "instances" / "vm.seed.yaml", "secret: value\n")
    _write(root / "overrides" / "ansible" / "inventory-overrides" / "production" / "group_vars.yml", "a: b\n")
    _write(root / "plugins" / "plugins.yaml", "schema_version: 1\nplugins: []\n")
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
    assert (output_root / "topology" / "instances").exists()
    assert (output_root / "secrets").exists()
    assert (output_root / "plugins").exists()
    assert (output_root / "plugins" / "plugins.yaml").exists()
    assert (output_root / "topology" / "product-bundles" / "default.yaml").exists()
    assert (output_root / "topology" / "product-profiles" / "default.yaml").exists()
    assert (output_root / "generated-artifacts").exists()
    assert (output_root / "BOOTSTRAP-NOTES.md").exists()
    assert (output_root / "Taskfile.yml").exists()
    assert (output_root / "taskfiles" / "project.yml").exists()


def test_bootstrap_project_repo_supports_extracted_framework_layout(tmp_path: Path) -> None:
    framework_root = _fake_extracted_framework_repo(tmp_path)
    output_root = tmp_path / "project-extracted"
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

    topology_payload = yaml.safe_load((output_root / "topology.yaml").read_text(encoding="utf-8"))
    framework_payload = topology_payload["framework"]
    assert framework_payload["class_modules_root"] == "framework/topology/class-modules"
    assert framework_payload["object_modules_root"] == "framework/topology/object-modules"
    assert (output_root / "framework.lock.yaml").exists()


def test_bootstrap_project_repo_can_wire_framework_submodule(tmp_path: Path) -> None:
    framework_root = _fake_extracted_framework_repo(tmp_path)
    _git_init_and_commit(framework_root)

    output_root = tmp_path / "project-submodule"
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
            "--init-git",
            "--framework-submodule-url",
            str(framework_root),
            "--framework-submodule-path",
            "framework",
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert (output_root / ".gitmodules").exists()
    assert (output_root / "framework" / "framework.yaml").exists()
    assert (output_root / "framework.lock.yaml").exists()


def test_bootstrap_project_repo_can_seed_project_data(tmp_path: Path) -> None:
    framework_root = _fake_extracted_framework_repo(tmp_path)
    seed_root = _fake_seed_project_root(tmp_path)
    output_root = tmp_path / "project-seeded"
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
            "--seed-project-root",
            str(seed_root),
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert (output_root / "topology" / "instances" / "compute" / "vm.seed.yaml").exists()
    assert (output_root / "secrets" / "instances" / "vm.seed.yaml").exists()
    assert (output_root / "overrides" / "ansible" / "inventory-overrides" / "production" / "group_vars.yml").exists()
    assert (output_root / "plugins" / "plugins.yaml").exists()


def test_bootstrap_project_repo_emits_mounted_framework_tool_commands(tmp_path: Path) -> None:
    framework_root = _fake_extracted_framework_repo(tmp_path)
    output_root = tmp_path / "project-notes"
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
            "--framework-submodule-path",
            "framework",
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr

    notes = (output_root / "BOOTSTRAP-NOTES.md").read_text(encoding="utf-8")
    assert "python framework/topology-tools/verify-framework-lock.py" in notes
    assert "python framework/topology-tools/compile-topology.py" in notes
    assert "--framework-manifest framework/framework.yaml" in notes

    project_taskfile = (output_root / "taskfiles" / "project.yml").read_text(encoding="utf-8")
    assert "{{.FRAMEWORK_TOOLS_ROOT}}/generate-framework-lock.py" in project_taskfile
    assert "{{.FRAMEWORK_TOOLS_ROOT}}/verify-framework-lock.py" in project_taskfile
    assert "{{.FRAMEWORK_TOOLS_ROOT}}/compile-topology.py" in project_taskfile
    assert "{{.FRAMEWORK_MANIFEST}}" in project_taskfile

    root_taskfile = (output_root / "Taskfile.yml").read_text(encoding="utf-8")
    assert "FRAMEWORK_TOOLS_ROOT: '{{default \"framework/topology-tools\" .FRAMEWORK_TOOLS_ROOT}}'" in root_taskfile
    assert "FRAMEWORK_MANIFEST: '{{default \"framework/framework.yaml\" .FRAMEWORK_MANIFEST}}'" in root_taskfile

#!/usr/bin/env python3
"""Integration tests for init-project-repo utility."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "topology-tools" / "utils" / "init-project-repo.py"


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
                        "topology/layer-contract.yaml",
                        "topology/class-modules",
                        "topology/object-modules",
                    ],
                },
            },
            sort_keys=False,
        ),
    )
    _write(
        root / "topology" / "layer-contract.yaml",
        yaml.safe_dump(
            {
                "schema_version": 1,
                "group_layers": {
                    "meta": "L0",
                    "devices": "L1",
                    "network": "L2",
                    "pools": "L3",
                    "data-assets": "L3",
                    "platform": "L4",
                    "service": "L5",
                    "monitoring": "L6",
                    "operations": "L7",
                },
            },
            sort_keys=False,
        ),
    )
    _write(root / "topology" / "class-modules" / ".gitkeep", "")
    _write(root / "topology" / "object-modules" / ".gitkeep", "")
    return root


def _fake_framework_distribution_zip(tmp_path: Path, *, version: str = "1.2.3") -> Path:
    dist_root = tmp_path / "dist-payload" / f"infra-topology-framework-{version}"
    _write(
        dist_root / "framework.yaml",
        yaml.safe_dump(
            {
                "schema_version": 1,
                "framework_id": "infra-topology-framework",
                "framework_api_version": "5.0.0",
                "supported_project_schema_range": ">=1.0.0 <2.0.0",
                "distribution": {
                    "layout_version": 1,
                    "include": [
                        "framework.yaml",
                        "topology/layer-contract.yaml",
                        "topology/model.lock.yaml",
                        "topology/profile-map.yaml",
                        "topology/class-modules",
                        "topology/object-modules",
                    ],
                },
            },
            sort_keys=False,
        ),
    )
    _write(
        dist_root / "topology" / "layer-contract.yaml",
        yaml.safe_dump(
            {
                "schema_version": 1,
                "group_layers": {
                    "firmware": "L1",
                    "power": "L1",
                },
            },
            sort_keys=False,
        ),
    )
    _write(dist_root / "topology" / "model.lock.yaml", "schema_version: 1\n")
    _write(dist_root / "topology" / "profile-map.yaml", "profiles: {}\n")
    _write(dist_root / "topology" / "class-modules" / ".gitkeep", "")
    _write(dist_root / "topology" / "object-modules" / ".gitkeep", "")

    zip_path = tmp_path / f"infra-topology-framework-{version}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(dist_root.rglob("*")):
            if not path.is_file():
                continue
            archive.write(path, arcname=path.relative_to(dist_root.parent).as_posix())
    return zip_path


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
    assert (output_root / "Taskfile.yml").exists()
    assert (output_root / "taskfiles" / "project.yml").exists()

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
        assert (output_root / "topology" / "instances" / bucket).exists()

    assert (
        output_root / "topology" / "instances" / "L1-foundation" / "firmware" / "inst.firmware.apc.backups.650va.yaml"
    ).exists()
    assert (output_root / "topology" / "instances" / "L1-foundation" / "power" / "ups-main.yaml").exists()


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


def test_init_project_repo_can_use_distribution_zip_package_dependency(tmp_path: Path) -> None:
    dist_zip = _fake_framework_distribution_zip(tmp_path, version="1.2.3")
    output_root = tmp_path / "project-from-dist"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-root",
            str(output_root),
            "--project-id",
            "home-lab",
            "--framework-dist-zip",
            str(dist_zip),
            "--skip-compile-check",
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert not (output_root / ".gitmodules").exists()
    assert (output_root / "framework" / "framework.yaml").exists()
    lock_payload = yaml.safe_load((output_root / "framework.lock.yaml").read_text(encoding="utf-8")) or {}
    framework_payload = lock_payload.get("framework", {})
    assert framework_payload.get("source") == "package"
    assert framework_payload.get("id") == "infra-topology-framework"
    assert framework_payload.get("version") == "1.2.3"
    assert isinstance(framework_payload.get("signature"), dict)
    assert isinstance(lock_payload.get("provenance"), dict)
    assert isinstance(lock_payload.get("sbom"), dict)


def test_init_project_repo_from_dist_emits_mounted_framework_commands(tmp_path: Path) -> None:
    dist_zip = _fake_framework_distribution_zip(tmp_path, version="1.2.3")
    output_root = tmp_path / "project-from-dist-commands"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-root",
            str(output_root),
            "--project-id",
            "home-lab",
            "--framework-dist-zip",
            str(dist_zip),
            "--framework-submodule-path",
            "framework",
            "--skip-compile-check",
            "--force",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr

    taskfile = (output_root / "taskfiles" / "project.yml").read_text(encoding="utf-8")
    assert "{{.FRAMEWORK_TOOLS_ROOT}}/generate-framework-lock.py" in taskfile
    assert "{{.FRAMEWORK_TOOLS_ROOT}}/verify-framework-lock.py" in taskfile
    assert "{{.FRAMEWORK_TOOLS_ROOT}}/compile-topology.py" in taskfile
    assert "{{.FRAMEWORK_MANIFEST}}" in taskfile

    root_taskfile = (output_root / "Taskfile.yml").read_text(encoding="utf-8")
    assert "FRAMEWORK_TOOLS_ROOT: '{{default \"framework/topology-tools\" .FRAMEWORK_TOOLS_ROOT}}'" in root_taskfile
    assert "FRAMEWORK_MANIFEST: '{{default \"framework/framework.yaml\" .FRAMEWORK_MANIFEST}}'" in root_taskfile

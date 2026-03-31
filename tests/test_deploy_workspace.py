from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.orchestration.deploy.workspace import resolve_deploy_workspace  # noqa: E402


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_resolve_deploy_workspace_main_repository_layout() -> None:
    workspace = resolve_deploy_workspace(repo_root=REPO_ROOT, project_id="home-lab")

    assert workspace.layout == "main_repository"
    assert workspace.repo_root == REPO_ROOT
    assert workspace.project_root == REPO_ROOT / "projects" / "home-lab"
    assert workspace.topology_path == REPO_ROOT / "topology" / "topology.yaml"
    assert workspace.framework_root == REPO_ROOT
    assert workspace.framework_tools_root == REPO_ROOT / "topology-tools"
    assert workspace.terraform_dir("proxmox") == "generated/home-lab/terraform/proxmox"
    assert workspace.ansible_cfg() == "projects/home-lab/ansible/ansible.cfg"


def test_resolve_deploy_workspace_project_repository_layout(tmp_path: Path) -> None:
    project_repo = tmp_path / "project-repo"
    framework_root = project_repo / "framework"
    _write_yaml(
        project_repo / "topology.yaml",
        {
            "version": "5.0.0",
            "project": {"active": "home-lab", "projects_root": "."},
            "framework": {"root": "framework"},
        },
    )
    _write_yaml(
        project_repo / "project.yaml",
        {
            "schema_version": 1,
            "project_schema_version": "1.0.0",
            "project": "home-lab",
            "project_min_framework_version": "5.0.0",
            "project_contract_revision": 1,
            "instances_root": "topology/instances",
            "secrets_root": "secrets",
        },
    )
    (framework_root / "topology-tools").mkdir(parents=True, exist_ok=True)
    (framework_root / "framework.yaml").write_text("schema_version: 1\nframework_id: test\n", encoding="utf-8")

    workspace = resolve_deploy_workspace(repo_root=project_repo, project_id="home-lab")

    assert workspace.layout == "project_repository"
    assert workspace.repo_root == project_repo
    assert workspace.project_root == project_repo
    assert workspace.topology_path == project_repo / "topology.yaml"
    assert workspace.framework_root == framework_root
    assert workspace.framework_tools_root == framework_root / "topology-tools"
    assert workspace.framework_lock_path == project_repo / "framework.lock.yaml"
    assert workspace.terraform_dir("mikrotik") == "generated/home-lab/terraform/mikrotik"
    assert workspace.ansible_cfg() == "ansible/ansible.cfg"


def test_resolve_deploy_workspace_project_repository_nested_project_root(tmp_path: Path) -> None:
    project_repo = tmp_path / "project-repo"
    framework_root = project_repo / "framework"
    _write_yaml(
        project_repo / "topology.yaml",
        {
            "version": "5.0.0",
            "project": {"active": "home-lab", "projects_root": "."},
            "framework": {"root": "framework"},
        },
    )
    _write_yaml(
        project_repo / "home-lab" / "project.yaml",
        {
            "schema_version": 1,
            "project_schema_version": "1.0.0",
            "project": "home-lab",
            "project_min_framework_version": "5.0.0",
            "project_contract_revision": 1,
            "instances_root": "topology/instances",
            "secrets_root": "secrets",
        },
    )
    (framework_root / "topology-tools").mkdir(parents=True, exist_ok=True)
    (framework_root / "framework.yaml").write_text("schema_version: 1\nframework_id: test\n", encoding="utf-8")

    workspace = resolve_deploy_workspace(repo_root=project_repo, project_id="home-lab")

    assert workspace.layout == "project_repository"
    assert workspace.project_root == project_repo / "home-lab"
    assert workspace.project_manifest_path == project_repo / "home-lab" / "project.yaml"

#!/usr/bin/env python3
"""Unit tests for service-chain evidence command planning."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

TOOLS_ROOT = Path(__file__).resolve().parents[1] / "topology-tools" / "utils"
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from service_chain_evidence import (  # noqa: E402
    CommandStep,
    StepResult,
    _resolve_path_argument,
    _resolve_path_argument_for_mode,
    build_command_plan,
    render_report,
)


def _joined(plan):
    return [" ".join(step.command) for step in plan]


def test_service_chain_plan_dry_mode_uses_check_tasks_only() -> None:
    plan = build_command_plan(mode="dry", project_id="home-lab", env="production", repo_root=REPO_ROOT)
    commands = _joined(plan)
    assert commands[0].startswith(sys.executable)
    assert "generate-framework-lock.py --repo-root ." in commands[0]
    assert any("--secrets-mode passthrough" in cmd for cmd in commands)
    assert any(cmd.startswith("bash -lc ") and "ansible-playbook" in cmd and " --check" in cmd for cmd in commands)
    assert not any(" terraform " in f" {cmd} " and " apply" in cmd for cmd in commands)


def test_service_chain_plan_maintenance_check_defaults_to_passthrough_mode() -> None:
    plan = build_command_plan(mode="maintenance-check", project_id="home-lab", env="production", repo_root=REPO_ROOT)
    commands = _joined(plan)
    assert any("--secrets-mode passthrough" in cmd for cmd in commands)
    assert any(cmd.startswith("bash -lc ") and "ansible-playbook" in cmd and " --check" in cmd for cmd in commands)
    assert any("terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false" == cmd for cmd in commands)


def test_service_chain_plan_maintenance_check_supports_inject_mode() -> None:
    plan = build_command_plan(
        mode="maintenance-check",
        project_id="home-lab",
        env="production",
        inject_secrets=True,
        repo_root=REPO_ROOT,
    )
    commands = _joined(plan)
    assert any("--secrets-mode inject" in cmd for cmd in commands)
    assert any(cmd.startswith("bash -lc ") and "ansible-playbook" in cmd and " --check" in cmd for cmd in commands)


def test_service_chain_plan_maintenance_apply_requires_allow_flag() -> None:
    with pytest.raises(ValueError):
        build_command_plan(mode="maintenance-apply", project_id="home-lab", env="production")


def test_service_chain_plan_deploy_runner_wsl_requires_repo_root() -> None:
    plan = build_command_plan(
        mode="maintenance-check",
        project_id="home-lab",
        env="production",
        deploy_runner="wsl",
        repo_root=REPO_ROOT,
    )
    assert plan


def test_service_chain_plan_ansible_via_wsl_alias_requires_repo_root() -> None:
    plan = build_command_plan(
        mode="maintenance-check",
        project_id="home-lab",
        env="production",
        ansible_via_wsl=True,
        repo_root=REPO_ROOT,
    )
    assert plan


def test_service_chain_plan_maintenance_apply_contains_apply_steps() -> None:
    plan = build_command_plan(
        mode="maintenance-apply",
        project_id="home-lab",
        env="production",
        allow_apply=True,
        repo_root=REPO_ROOT,
    )
    commands = _joined(plan)
    assert any("terraform -chdir=generated/home-lab/terraform/proxmox apply" == cmd for cmd in commands)
    assert any("terraform -chdir=generated/home-lab/terraform/mikrotik apply" == cmd for cmd in commands)
    assert any(cmd.startswith("bash -lc ") and "ansible-playbook" in cmd and " --check" not in cmd for cmd in commands)


def test_service_chain_plan_maintenance_check_supports_deploy_runner_wsl_commands() -> None:
    plan = build_command_plan(
        mode="maintenance-check",
        project_id="home-lab",
        env="production",
        deploy_runner="wsl",
        repo_root=REPO_ROOT,
    )
    commands = _joined(plan)
    assert any(cmd.startswith("bash -lc ") and "--syntax-check" in cmd for cmd in commands)
    assert any(cmd.startswith("bash -lc ") and " --check" in cmd for cmd in commands)


def test_service_chain_plan_ansible_via_wsl_alias_maps_to_wsl_runner() -> None:
    plan = build_command_plan(
        mode="maintenance-check",
        project_id="home-lab",
        env="production",
        ansible_via_wsl=True,
        repo_root=REPO_ROOT,
    )
    commands = _joined(plan)
    assert any(cmd.startswith("bash -lc ") and "--syntax-check" in cmd for cmd in commands)


def test_service_chain_plan_rejects_conflicting_runner_and_wsl_alias() -> None:
    with pytest.raises(ValueError):
        build_command_plan(
            mode="maintenance-check",
            project_id="home-lab",
            env="production",
            deploy_runner="wsl",
            ansible_via_wsl=True,
            repo_root=REPO_ROOT,
        )


def test_service_chain_plan_maintenance_apply_supports_auto_approve() -> None:
    plan = build_command_plan(
        mode="maintenance-apply",
        project_id="home-lab",
        env="production",
        allow_apply=True,
        terraform_auto_approve=True,
        repo_root=REPO_ROOT,
    )
    commands = _joined(plan)
    assert any("terraform -chdir=generated/home-lab/terraform/proxmox apply -auto-approve" == cmd for cmd in commands)
    assert any("terraform -chdir=generated/home-lab/terraform/mikrotik apply -auto-approve" == cmd for cmd in commands)


def test_service_chain_plan_uses_backend_config_when_provided() -> None:
    plan = build_command_plan(
        mode="maintenance-check",
        project_id="home-lab",
        env="production",
        proxmox_backend_config="projects/home-lab/secrets/terraform/proxmox.backend.tfbackend",
        mikrotik_backend_config="projects/home-lab/secrets/terraform/mikrotik.backend.tfbackend",
        repo_root=REPO_ROOT,
    )
    commands = _joined(plan)
    assert any(
        "-backend-config projects/home-lab/secrets/terraform/proxmox.backend.tfbackend" in cmd for cmd in commands
    )
    assert any(
        "-backend-config projects/home-lab/secrets/terraform/mikrotik.backend.tfbackend" in cmd for cmd in commands
    )


def test_service_chain_plan_uses_var_files_when_provided() -> None:
    plan = build_command_plan(
        mode="maintenance-check",
        project_id="home-lab",
        env="production",
        proxmox_var_file="projects/home-lab/secrets/terraform/proxmox.auto.tfvars",
        mikrotik_var_file="projects/home-lab/secrets/terraform/mikrotik.auto.tfvars",
        repo_root=REPO_ROOT,
    )
    commands = _joined(plan)
    assert any("-var-file projects/home-lab/secrets/terraform/proxmox.auto.tfvars" in cmd for cmd in commands)
    assert any("-var-file projects/home-lab/secrets/terraform/mikrotik.auto.tfvars" in cmd for cmd in commands)


def test_resolve_path_argument_converts_relative_to_absolute(tmp_path: Path) -> None:
    resolved = _resolve_path_argument("projects/home-lab/secrets/terraform/proxmox.auto.tfvars", tmp_path)
    assert resolved == str((tmp_path / "projects/home-lab/secrets/terraform/proxmox.auto.tfvars").resolve())
    assert _resolve_path_argument("", tmp_path) is None


def test_resolve_path_argument_preserves_relative_in_bundle_mode(tmp_path: Path) -> None:
    resolved = _resolve_path_argument_for_mode(
        "artifacts/generated/terraform/proxmox/terraform.tfvars.example",
        tmp_path,
        preserve_relative=True,
    )
    assert resolved == "artifacts/generated/terraform/proxmox/terraform.tfvars.example"


def test_resolve_path_argument_preserves_and_normalizes_windows_relative_in_bundle_mode(tmp_path: Path) -> None:
    resolved = _resolve_path_argument_for_mode(
        r"artifacts\generated\terraform\mikrotik\terraform.tfvars.example",
        tmp_path,
        preserve_relative=True,
    )
    assert resolved == "artifacts/generated/terraform/mikrotik/terraform.tfvars.example"


def test_service_chain_plan_project_repository_uses_framework_tool_mount(tmp_path: Path) -> None:
    project_repo = tmp_path / "project-repo"
    (project_repo / "framework" / "topology-tools").mkdir(parents=True, exist_ok=True)
    (project_repo / "framework" / "framework.yaml").write_text(
        "schema_version: 1\nframework_id: test\n", encoding="utf-8"
    )
    (project_repo / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "project_schema_version": "1.0.0",
                "project": "home-lab",
                "project_min_framework_version": "5.0.0",
                "project_contract_revision": 1,
                "instances_root": "topology/instances",
                "secrets_root": "secrets",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_repo / "topology.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "5.0.0",
                "project": {"active": "home-lab", "projects_root": "."},
                "framework": {"root": "framework"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    plan = build_command_plan(mode="maintenance-check", project_id="home-lab", env="production", repo_root=project_repo)
    commands = _joined(plan)

    assert any("framework/topology-tools/generate-framework-lock.py --repo-root ." in cmd for cmd in commands)
    assert any(
        "framework/topology-tools/compile-topology.py --repo-root . --topology topology.yaml" in cmd for cmd in commands
    )
    assert any("terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false" == cmd for cmd in commands)
    assert any("ansible/ansible.cfg" in cmd for cmd in commands)


def test_render_report_includes_stdout_and_stderr_in_failure_details() -> None:
    step = CommandStep(id="ansible.execute", description="Run ansible", command=["ansible-playbook"])
    result = StepResult(
        step=step,
        returncode=4,
        duration_s=1.0,
        stdout="PLAY RECAP ... host unreachable",
        stderr="[DEPRECATION WARNING] ...",
    )
    report = render_report(
        mode="maintenance-check",
        operator="tester",
        commit_sha="deadbeef",
        project_id="home-lab",
        env="production",
        steps=[step],
        results=[result],
        plan_only=False,
    )
    assert "[stdout]" in report
    assert "host unreachable" in report
    assert "[stderr]" in report
    assert "DEPRECATION WARNING" in report

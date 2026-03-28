#!/usr/bin/env python3
"""Unit tests for service-chain evidence command planning."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS_ROOT = Path(__file__).resolve().parents[1] / "topology-tools"
sys.path.insert(0, str(TOOLS_ROOT))

from service_chain_evidence import _resolve_path_argument, build_command_plan  # noqa: E402


def _joined(plan):
    return [" ".join(step.command) for step in plan]


def test_service_chain_plan_dry_mode_uses_check_tasks_only() -> None:
    plan = build_command_plan(mode="dry", project_id="home-lab", env="production")
    commands = _joined(plan)
    assert commands[0] == "task framework:lock-refresh"
    assert any("--secrets-mode passthrough" in cmd for cmd in commands)
    assert any("task ansible:runtime" == cmd for cmd in commands)
    assert any("task ansible:check-site" == cmd for cmd in commands)
    assert not any("ansible:apply-site-inject" in cmd for cmd in commands)
    assert not any(" terraform " in f" {cmd} " and " apply" in cmd for cmd in commands)


def test_service_chain_plan_maintenance_check_defaults_to_passthrough_mode() -> None:
    plan = build_command_plan(mode="maintenance-check", project_id="home-lab", env="production")
    commands = _joined(plan)
    assert any("--secrets-mode passthrough" in cmd for cmd in commands)
    assert any("task ansible:runtime" == cmd for cmd in commands)
    assert any("task ansible:check-site" == cmd for cmd in commands)
    assert any("terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false" == cmd for cmd in commands)
    assert not any("ansible:apply-site" in cmd for cmd in commands)


def test_service_chain_plan_maintenance_check_supports_inject_mode() -> None:
    plan = build_command_plan(mode="maintenance-check", project_id="home-lab", env="production", inject_secrets=True)
    commands = _joined(plan)
    assert any("--secrets-mode inject" in cmd for cmd in commands)
    assert any("task ansible:runtime-inject" == cmd for cmd in commands)
    assert any("task ansible:check-site-inject" == cmd for cmd in commands)


def test_service_chain_plan_maintenance_apply_requires_allow_flag() -> None:
    with pytest.raises(ValueError):
        build_command_plan(mode="maintenance-apply", project_id="home-lab", env="production")


def test_service_chain_plan_maintenance_apply_contains_apply_steps() -> None:
    plan = build_command_plan(mode="maintenance-apply", project_id="home-lab", env="production", allow_apply=True)
    commands = _joined(plan)
    assert any("terraform -chdir=generated/home-lab/terraform/proxmox apply" == cmd for cmd in commands)
    assert any("terraform -chdir=generated/home-lab/terraform/mikrotik apply" == cmd for cmd in commands)
    assert any("task ansible:apply-site" == cmd for cmd in commands)


def test_service_chain_plan_maintenance_apply_supports_auto_approve() -> None:
    plan = build_command_plan(
        mode="maintenance-apply",
        project_id="home-lab",
        env="production",
        allow_apply=True,
        terraform_auto_approve=True,
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
    )
    commands = _joined(plan)
    assert any("-var-file projects/home-lab/secrets/terraform/proxmox.auto.tfvars" in cmd for cmd in commands)
    assert any("-var-file projects/home-lab/secrets/terraform/mikrotik.auto.tfvars" in cmd for cmd in commands)


def test_resolve_path_argument_converts_relative_to_absolute(tmp_path: Path) -> None:
    resolved = _resolve_path_argument("projects/home-lab/secrets/terraform/proxmox.auto.tfvars", tmp_path)
    assert resolved == str((tmp_path / "projects/home-lab/secrets/terraform/proxmox.auto.tfvars").resolve())
    assert _resolve_path_argument("", tmp_path) is None

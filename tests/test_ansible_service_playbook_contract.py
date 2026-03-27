#!/usr/bin/env python3
"""Contract checks for project-scoped Ansible service integration."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_ansible_service_playbook_layout_exists() -> None:
    root = _repo_root() / "projects" / "home-lab" / "ansible"
    required_files = [
        root / "ansible.cfg",
        root / "README.md",
        root / "playbooks" / "site.yml",
        root / "playbooks" / "common.yml",
        root / "playbooks" / "postgresql.yml",
        root / "playbooks" / "redis.yml",
        root / "playbooks" / "nextcloud.yml",
        root / "playbooks" / "monitoring.yml",
        root / "group_vars" / "all" / "vars.yml",
        root / "group_vars" / "all" / "vault.example.yml",
    ]
    for path in required_files:
        assert path.exists(), f"missing expected ansible file: {path}"


def test_ansible_service_roles_exist() -> None:
    roles_root = _repo_root() / "projects" / "home-lab" / "ansible" / "roles"
    required_role_files = [
        roles_root / "common" / "tasks" / "main.yml",
        roles_root / "postgresql" / "tasks" / "main.yml",
        roles_root / "redis" / "tasks" / "main.yml",
        roles_root / "nextcloud" / "tasks" / "main.yml",
        roles_root / "monitoring_stack" / "tasks" / "main.yml",
    ]
    for path in required_role_files:
        assert path.exists(), f"missing expected ansible role task file: {path}"


def test_playbooks_do_not_depend_on_archive_paths_or_legacy_groups() -> None:
    playbook_root = _repo_root() / "projects" / "home-lab" / "ansible" / "playbooks"
    for playbook in playbook_root.glob("*.yml"):
        content = playbook.read_text(encoding="utf-8")
        assert "archive/v4" not in content, f"{playbook} contains archive dependency"
        assert "lxc_containers" not in content, f"{playbook} uses legacy group lxc_containers"

    site_content = (playbook_root / "site.yml").read_text(encoding="utf-8")
    assert "import_playbook: monitoring.yml" in site_content

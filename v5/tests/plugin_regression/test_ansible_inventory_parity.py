#!/usr/bin/env python3
"""Parity checks for v5 Ansible inventory core contract vs v4 baseline."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
V4_INVENTORY_ROOT = REPO_ROOT / "v4-generated" / "ansible" / "inventory" / "production"


def _hosts(node: dict, *path: str) -> set[str]:
    cursor = node
    for key in path:
        cursor = cursor.get(key, {}) if isinstance(cursor, dict) else {}
    if not isinstance(cursor, dict):
        return set()
    return set(cursor.keys())


def test_ansible_inventory_core_files_exist(generated_artifacts_root: Path) -> None:
    v5_root = generated_artifacts_root / "ansible" / "inventory" / "production"
    assert (v5_root / "hosts.yml").exists()
    assert (v5_root / "group_vars" / "all.yml").exists()


def test_ansible_inventory_lxc_hosts_match_v4_baseline(generated_artifacts_root: Path) -> None:
    v5_root = generated_artifacts_root / "ansible" / "inventory" / "production"
    v4_hosts_path = V4_INVENTORY_ROOT / "hosts.yml"
    if not v4_hosts_path.exists():
        pytest.skip(f"v4 inventory baseline missing: {v4_hosts_path}")
    v4_hosts = yaml.safe_load(v4_hosts_path.read_text(encoding="utf-8")) or {}
    v5_hosts = yaml.safe_load((v5_root / "hosts.yml").read_text(encoding="utf-8")) or {}

    v4_lxc_hosts = _hosts(v4_hosts, "all", "children", "lxc_containers", "hosts")
    v5_lxc_hosts = _hosts(v5_hosts, "all", "children", "lxc", "hosts")
    assert v5_lxc_hosts == v4_lxc_hosts


def test_ansible_inventory_host_vars_intentional_extension(generated_artifacts_root: Path) -> None:
    """Intentional diff vs v4: v5 exports host_vars per host for deterministic downstream wiring."""
    v5_root = generated_artifacts_root / "ansible" / "inventory" / "production"
    host_vars_files = sorted((v5_root / "host_vars").glob("*.yml"))
    assert host_vars_files, "v5 host_vars extension is expected and must not be empty"


def test_ansible_inventory_semantic_contract(generated_artifacts_root: Path) -> None:
    v5_root = generated_artifacts_root / "ansible" / "inventory" / "production"
    group_vars = yaml.safe_load((v5_root / "group_vars" / "all.yml").read_text(encoding="utf-8")) or {}
    hosts_payload = yaml.safe_load((v5_root / "hosts.yml").read_text(encoding="utf-8")) or {}

    assert group_vars.get("topology_lane") == "v5"
    assert group_vars.get("inventory_profile") == "production"
    assert "inventory_host_count" in group_vars
    assert "all" in hosts_payload
    assert "children" in hosts_payload["all"]


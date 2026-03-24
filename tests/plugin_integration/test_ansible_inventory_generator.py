#!/usr/bin/env python3
"""Integration checks for Ansible inventory generator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from plugins.generators.ansible_inventory_generator import AnsibleInventoryGenerator


def _ctx(tmp_path: Path, compiled_json: dict) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=compiled_json,
        output_dir=str(tmp_path / "build"),
        config={"generator_artifacts_root": str(tmp_path / "generated")},
    )


def _compiled_fixture() -> dict:
    return {
        "instances": {
            "devices": [
                {"instance_id": "srv-gamayun", "object_ref": "obj.proxmox.ve"},
                {"instance_id": "rtr-mk", "object_ref": "obj.mikrotik.chateau_lte7_ax"},
            ],
            "lxc": [
                {"instance_id": "lxc-redis", "object_ref": "obj.proxmox.lxc.debian12.redis"},
            ],
        }
    }


def test_ansible_inventory_generator_writes_expected_files(tmp_path: Path) -> None:
    generator = AnsibleInventoryGenerator("base.generator.ansible_inventory")
    ctx = _ctx(tmp_path, _compiled_fixture())

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    root = tmp_path / "generated" / "ansible" / "inventory" / "production"
    assert (root / "hosts.yml").exists()
    assert (root / "group_vars" / "all.yml").exists()
    assert (root / "host_vars" / "lxc-redis.yml").exists()
    assert (root / "host_vars" / "rtr-mk.yml").exists()
    assert (root / "host_vars" / "srv-gamayun.yml").exists()

    hosts_payload = yaml.safe_load((root / "hosts.yml").read_text(encoding="utf-8"))
    children = hosts_payload["all"]["children"]
    assert list(children["devices"]["hosts"].keys()) == ["rtr-mk", "srv-gamayun"]
    assert list(children["lxc"]["hosts"].keys()) == ["lxc-redis"]


def test_ansible_inventory_generator_reports_projection_error(tmp_path: Path) -> None:
    generator = AnsibleInventoryGenerator("base.generator.ansible_inventory")
    ctx = _ctx(tmp_path, {"instances": {"devices": [{}]}})

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9301" for diag in result.diagnostics)

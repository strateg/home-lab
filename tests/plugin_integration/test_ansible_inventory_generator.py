#!/usr/bin/env python3
"""Integration checks for Ansible inventory generator plugin."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from plugins.generators.ansible_inventory_generator import AnsibleInventoryGenerator


def _semanticize(compiled_json: dict) -> dict:
    payload = copy.deepcopy(compiled_json)
    instances = payload.get("instances")
    if not isinstance(instances, dict):
        return payload
    for rows in instances.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            object_ref = row.pop("object_ref", None)
            class_ref = row.pop("class_ref", None)
            if not isinstance(object_ref, str) and not isinstance(class_ref, str):
                continue
            instance_block = row.get("instance")
            if not isinstance(instance_block, dict):
                instance_block = {}
                row["instance"] = instance_block
            if isinstance(object_ref, str) and object_ref:
                instance_block.setdefault("materializes_object", object_ref)
            if isinstance(class_ref, str) and class_ref:
                instance_block.setdefault("materializes_class", class_ref)
    return payload


def _ctx(tmp_path: Path, compiled_json: dict) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=_semanticize(compiled_json),
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

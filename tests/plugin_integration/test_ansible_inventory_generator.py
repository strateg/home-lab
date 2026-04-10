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


def _ctx(tmp_path: Path, compiled_json: dict, *, artifacts_root: Path | None = None) -> PluginContext:
    root = artifacts_root or (tmp_path / "generated")
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=_semanticize(compiled_json),
        output_dir=str(tmp_path / "build"),
        config={"generator_artifacts_root": str(root)},
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
    assert result.output_data is not None
    assert result.output_data["artifact_plan"]["artifact_family"] == "ansible.inventory"
    assert result.output_data["artifact_generation_report"]["summary"]["generated_count"] == len(
        result.output_data["ansible_inventory_files"]
    )
    planned_paths = [str(item.get("path", "")) for item in result.output_data["artifact_plan"]["planned_outputs"]]
    assert planned_paths
    assert all(path.startswith("generated/") for path in planned_paths)
    assert all(not path.startswith(str(tmp_path)) for path in planned_paths)
    generated_paths = list(result.output_data["artifact_generation_report"].get("generated", []))
    assert generated_paths
    assert all(path.startswith("generated/") for path in generated_paths)
    assert all(not path.startswith(str(tmp_path)) for path in generated_paths)
    for contract_file in result.output_data["artifact_contract_files"]:
        assert Path(contract_file).exists()

    hosts_payload = yaml.safe_load((root / "hosts.yml").read_text(encoding="utf-8"))
    children = hosts_payload["all"]["children"]
    assert list(children["devices"]["hosts"].keys()) == ["rtr-mk", "srv-gamayun"]
    assert list(children["lxc"]["hosts"].keys()) == ["lxc-redis"]


def test_ansible_inventory_artifact_plan_includes_group_vars_output(tmp_path: Path) -> None:
    generator = AnsibleInventoryGenerator("base.generator.ansible_inventory")
    ctx = _ctx(tmp_path, _compiled_fixture())

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    artifact_plan = result.output_data["artifact_plan"]
    planned_paths = [str(item.get("path", "")) for item in artifact_plan.get("planned_outputs", [])]
    assert any(path.endswith("/group_vars/all.yml") for path in planned_paths)
    assert all(item.get("renderer") == "structured" for item in artifact_plan.get("planned_outputs", []))


def test_ansible_inventory_artifact_plan_is_logical_when_artifacts_root_is_custom(tmp_path: Path) -> None:
    generator = AnsibleInventoryGenerator("base.generator.ansible_inventory")
    custom_root = tmp_path / "build" / "cutover" / "split-rehearsal" / "generated-artifacts"
    ctx = _ctx(tmp_path, _compiled_fixture(), artifacts_root=custom_root)

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    planned_paths = [str(item.get("path", "")) for item in result.output_data["artifact_plan"]["planned_outputs"]]
    assert planned_paths
    assert all(path.startswith("generated/") for path in planned_paths)
    assert all("split-rehearsal" not in path for path in planned_paths)
    assert all(not path.startswith(str(tmp_path)) for path in planned_paths)


def test_ansible_inventory_obsolete_delete_uses_ownership_proof(tmp_path: Path) -> None:
    generator = AnsibleInventoryGenerator("base.generator.ansible_inventory")
    ctx = _ctx(tmp_path, _compiled_fixture())
    ctx.config["artifact_obsolete_action"] = "delete"

    stale_path = tmp_path / "generated" / "ansible" / "inventory" / "production" / "stale.yml"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("# stale\n", encoding="utf-8")

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    obsolete = result.output_data["artifact_generation_report"]["obsolete"]
    stale_entry = next(item for item in obsolete if item["path"] == "generated/ansible/inventory/production/stale.yml")
    assert stale_entry["action"] == "delete"
    assert stale_entry["ownership_proven"] is True
    assert stale_entry["ownership_method"] == "output_prefix_match"


def test_ansible_inventory_records_stale_host_vars_without_unlink(tmp_path: Path) -> None:
    generator = AnsibleInventoryGenerator("base.generator.ansible_inventory")
    ctx = _ctx(tmp_path, _compiled_fixture())

    stale_path = tmp_path / "generated" / "ansible" / "inventory" / "production" / "host_vars" / "removed.yml"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("# stale\n", encoding="utf-8")

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    assert stale_path.exists()
    obsolete = result.output_data["artifact_generation_report"]["obsolete"]
    stale_entry = next(
        item for item in obsolete if item["path"] == "generated/ansible/inventory/production/host_vars/removed.yml"
    )
    assert stale_entry["action"] == "warn"


def test_ansible_inventory_generator_reports_projection_error(tmp_path: Path) -> None:
    generator = AnsibleInventoryGenerator("base.generator.ansible_inventory")
    ctx = _ctx(tmp_path, {"instances": {"devices": [{}]}})

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9301" for diag in result.diagnostics)

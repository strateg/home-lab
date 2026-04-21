#!/usr/bin/env python3
"""Integration tests for network vlan tags validator plugin."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.network_vlan_tags"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _objects() -> dict:
    return {
        "obj.bridge.a": {"class_ref": "class.network.bridge", "properties": {"vlan_aware": True}},
        "obj.bridge.b": {"class_ref": "class.network.bridge", "properties": {"vlan_aware": False}},
        "obj.vlan.a": {"class_ref": "class.network.vlan", "properties": {"vlan_id": 30, "bridge_ref": "inst.bridge.a"}},
        "obj.workload.a": {"class_ref": "class.compute.workload.lxc", "properties": {}},
    }


def _rows() -> list[dict]:
    return [
        {
            "group": "network",
            "instance": "inst.bridge.a",
            "class_ref": "class.network.bridge",
            "layer": "L2",
            "object_ref": "obj.bridge.a",
        },
        {
            "group": "network",
            "instance": "inst.bridge.b",
            "class_ref": "class.network.bridge",
            "layer": "L2",
            "object_ref": "obj.bridge.b",
        },
        {
            "group": "network",
            "instance": "inst.vlan.a",
            "class_ref": "class.network.vlan",
            "layer": "L2",
            "object_ref": "obj.vlan.a",
        },
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "object_ref": "obj.workload.a",
            "extensions": {"networks": [{"network_ref": "inst.vlan.a", "vlan_tag": 30}]},
        },
    ]


def test_network_vlan_tags_validator_manifest_requires_normalized_rows() -> None:
    registry = _registry()
    normalized_rows = registry.specs[PLUGIN_ID].consumes[0]
    assert normalized_rows["required"] is True


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects=copy.deepcopy(_objects()),
        instance_bindings={"instance_bindings": {}},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)


def test_network_vlan_tags_validator_accepts_matching_vlan_tag():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_vlan_tags_validator_rejects_mismatched_vlan_tag():
    registry = _registry()
    ctx = _context()
    rows = _rows()
    rows[-1]["extensions"]["networks"][0]["vlan_tag"] = 99  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7838" for diag in result.diagnostics)


def test_network_vlan_tags_validator_warns_on_non_vlan_aware_bridge():
    registry = _registry()
    ctx = _context()
    rows = _rows()
    rows[-1]["extensions"]["networks"][0]["bridge_ref"] = "inst.bridge.b"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7839" for diag in result.diagnostics)


def test_network_vlan_tags_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)


def test_network_vlan_tags_validator_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    spec = _registry().specs[PLUGIN_ID]
    rel_entry, class_name = spec.entry.split(":", 1)
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.instance_rows",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / "plugins/compilers/instance_rows_compiler.py").as_posix()}:InstanceRowsCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 43,
            },
            {
                "id": PLUGIN_ID,
                "kind": spec.kind.value,
                "entry": f"{(V5_TOOLS / "plugins" / rel_entry).as_posix()}:{class_name}",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": spec.phase.value,
                "order": spec.order,
                "depends_on": list(spec.depends_on),
                "consumes": [
                    {"from_plugin": "base.compiler.instance_rows", "key": "normalized_rows", "required": True}
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = _context()

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)
    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in results[0].diagnostics)

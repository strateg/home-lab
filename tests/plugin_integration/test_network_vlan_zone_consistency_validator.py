#!/usr/bin/env python3
"""Integration tests for VLAN/trust-zone consistency validator plugin."""

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

PLUGIN_ID = "base.validator.network_vlan_zone_consistency"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _objects() -> dict:
    return {
        "obj.network.vlan.a": {
            "class_ref": "class.network.vlan",
            "properties": {"vlan_id": 30, "trust_zone_ref": "inst.zone.a"},
        },
        "obj.network.zone.a": {
            "class_ref": "class.network.trust_zone",
            "properties": {"vlan_ids": [30, 40]},
        },
    }


def _rows() -> list[dict]:
    return [
        {
            "group": "network",
            "instance": "inst.zone.a",
            "class_ref": "class.network.trust_zone",
            "object_ref": "obj.network.zone.a",
        },
        {
            "group": "network",
            "instance": "inst.vlan.a",
            "class_ref": "class.network.vlan",
            "object_ref": "obj.network.vlan.a",
        },
    ]


def test_network_vlan_zone_consistency_validator_manifest_requires_normalized_rows() -> None:
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


def test_network_vlan_zone_consistency_validator_accepts_matching_vlan_id():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_vlan_zone_consistency_validator_warns_on_vlan_id_mismatch():
    registry = _registry()
    ctx = _context()
    ctx.objects["obj.network.zone.a"]["properties"]["vlan_ids"] = [40, 50]  # type: ignore[index]
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7830" for diag in result.diagnostics)


def test_network_vlan_zone_consistency_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)

def test_network_vlan_zone_consistency_validator_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
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


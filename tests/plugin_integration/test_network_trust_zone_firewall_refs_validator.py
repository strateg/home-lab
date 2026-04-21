#!/usr/bin/env python3
"""Integration tests for trust-zone firewall refs validator plugin."""

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

PLUGIN_ID = "base.validator.network_trust_zone_firewall_refs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_network_trust_zone_firewall_refs_manifest_requires_normalized_rows() -> None:
    registry = _registry()
    normalized_rows = registry.specs[PLUGIN_ID].consumes[0]
    assert normalized_rows["required"] is True


def _objects() -> dict:
    return {
        "obj.network.trust_zone.a": {
            "class_ref": "class.network.trust_zone",
            "properties": {"default_firewall_policy_ref": "inst.fw.policy.a"},
        },
        "obj.network.firewall_policy.a": {
            "class_ref": "class.network.firewall_policy",
            "properties": {"name": "allow-core"},
        },
    }


def _rows() -> list[dict]:
    return [
        {
            "group": "network",
            "instance": "inst.zone.a",
            "class_ref": "class.network.trust_zone",
            "object_ref": "obj.network.trust_zone.a",
        },
        {
            "group": "network",
            "instance": "inst.fw.policy.a",
            "class_ref": "class.network.firewall_policy",
            "object_ref": "obj.network.firewall_policy.a",
        },
    ]


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


def test_network_trust_zone_firewall_refs_validator_accepts_valid_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_trust_zone_firewall_refs_validator_rejects_missing_target():
    registry = _registry()
    ctx = _context()
    rows = [row for row in _rows() if row["instance"] != "inst.fw.policy.a"]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7822" for diag in result.diagnostics)


def test_network_trust_zone_firewall_refs_validator_rejects_wrong_target_class():
    registry = _registry()
    ctx = _context()
    rows = _rows()
    rows[1]["class_ref"] = "class.network.vlan"
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7822" for diag in result.diagnostics)


def test_network_trust_zone_firewall_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)


def test_network_trust_zone_firewall_refs_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.instance_rows",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/instance_rows_compiler.py').as_posix()}:InstanceRowsCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 43,
            },
            {
                "id": PLUGIN_ID,
                "kind": "validator_json",
                "entry": f"{(V5_TOOLS / 'plugins/validators/network_trust_zone_firewall_refs_validator.py').as_posix()}:NetworkTrustZoneFirewallRefsValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 119,
                "depends_on": ["base.compiler.instance_rows"],
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

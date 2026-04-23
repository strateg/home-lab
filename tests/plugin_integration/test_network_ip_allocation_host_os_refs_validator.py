#!/usr/bin/env python3
"""Integration tests for network ip_allocation host_os_ref validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.network_ip_allocation_host_os_refs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_network_ip_allocation_host_os_refs_manifest_requires_normalized_rows() -> None:
    registry = _registry()
    normalized_rows = registry.specs[PLUGIN_ID].consumes[0]
    assert normalized_rows["required"] is True


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)


def test_network_ip_allocation_host_os_refs_validator_rejects_host_os_ref_in_mode_h():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os"},
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "os_refs": ["inst.os.a"]},
            {
                "group": "network",
                "instance": "inst.vlan.a",
                "class_ref": "class.network.vlan",
                "extensions": {
                    "ip_allocations": [{"ip": "10.0.30.10", "device_ref": "srv-a", "host_os_ref": "inst.os.a"}]
                },
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7827" and "forbidden in Mode H" in diag.message for diag in result.diagnostics)


def test_network_ip_allocation_host_os_refs_validator_rejects_unknown_host_os_ref_by_forbidden_rule():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "network",
                "instance": "inst.vlan.a",
                "class_ref": "class.network.vlan",
                "extensions": {
                    "ip_allocations": [
                        {"ip": "10.0.30.10", "device_ref": "srv-a", "host_os_ref": "inst.os.missing"},
                    ]
                },
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7827" for diag in result.diagnostics)


def test_network_ip_allocation_host_os_refs_validator_accepts_device_ref_without_host_os_ref_mode_h():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os"},
            {
                "group": "network",
                "instance": "inst.vlan.a",
                "class_ref": "class.network.vlan",
                "extensions": {"ip_allocations": [{"ip": "10.0.30.10", "device_ref": "srv-a"}]},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_ip_allocation_host_os_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)


def test_network_ip_allocation_host_os_refs_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
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
                "entry": f"{(V5_TOOLS / 'plugins/validators/network_ip_allocation_host_os_refs_validator.py').as_posix()}:NetworkIpAllocationHostOsRefsValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 124,
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


def test_network_ip_allocation_host_os_refs_validator_requires_device_ref():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os"},
            {
                "group": "network",
                "instance": "inst.vlan.a",
                "class_ref": "class.network.vlan",
                "extensions": {"ip_allocations": [{"ip": "10.0.30.10"}]},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7827" for diag in result.diagnostics)


def test_network_ip_allocation_host_os_refs_validator_supports_top_level_payload():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os"},
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "os_refs": ["inst.os.a"]},
            {
                "group": "network",
                "instance": "inst.vlan.a",
                "class_ref": "class.network.vlan",
                "ip_allocations": [{"ip": "10.0.30.10", "device_ref": "srv-a"}],
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_ip_allocation_host_os_refs_validator_supports_non_vlan_legacy_shape():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os"},
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "os_refs": ["inst.os.a"]},
            {
                "group": "network",
                "instance": "inst.net.segment.a",
                "class_ref": "class.network.segment",
                "ip_allocations": [{"ip": "10.0.30.10", "device_ref": "srv-a", "host_os_ref": "inst.os.a"}],
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7827" and "forbidden in Mode H" in diag.message for diag in result.diagnostics)

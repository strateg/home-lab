#!/usr/bin/env python3
"""Integration tests for runtime network reachability validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.network_runtime_reachability"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_network_runtime_reachability_validator_manifest_requires_normalized_rows() -> None:
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


def _base_rows() -> list[dict]:
    return [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1", "os_refs": ["inst.os.a"]},
        {"group": "os", "instance": "inst.os.a", "class_ref": "class.os", "layer": "L1", "status": "active"},
        {
            "group": "network",
            "instance": "inst.vlan.a",
            "class_ref": "class.network.vlan",
            "layer": "L2",
            "extensions": {"ip_allocations": [{"device_ref": "srv-a", "host_os_ref": "inst.os.a"}]},
        },
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {"networks": [{"network_ref": "inst.vlan.a"}]},
        },
        {
            "group": "services",
            "instance": "svc-a",
            "class_ref": "class.service.monitoring",
            "layer": "L5",
            "runtime": {"type": "lxc", "target_ref": "lxc-a", "network_binding_ref": "inst.vlan.a"},
        },
    ]


def test_network_runtime_reachability_validator_accepts_lxc_with_network_attachment():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_runtime_reachability_validator_warns_on_lxc_network_mismatch():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[3]["extensions"]["networks"][0]["network_ref"] = "inst.vlan.other"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7844" for diag in result.diagnostics)


def test_network_runtime_reachability_validator_warns_on_unreachable_docker_target():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["runtime"] = {"type": "docker", "target_ref": "srv-b", "network_binding_ref": "inst.vlan.a"}
    rows.append({"group": "devices", "instance": "srv-b", "class_ref": "class.router", "layer": "L1", "os_refs": []})
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7844" for diag in result.diagnostics)


def test_network_runtime_reachability_validator_accepts_reachable_docker_target():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["runtime"] = {"type": "docker", "target_ref": "srv-a", "network_binding_ref": "inst.vlan.a"}
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_runtime_reachability_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)


def test_network_runtime_reachability_validator_supports_top_level_network_fields():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[2].pop("extensions")  # type: ignore[index]
    rows[2]["ip_allocations"] = [{"device_ref": "srv-a", "host_os_ref": "inst.os.a"}]  # type: ignore[index]
    rows[3].pop("extensions")  # type: ignore[index]
    rows[3]["networks"] = [{"network_ref": "inst.vlan.a"}]  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_runtime_reachability_validator_treats_mapped_host_os_as_unreachable():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["status"] = "mapped"  # type: ignore[index]
    rows[-1]["runtime"] = {"type": "docker", "target_ref": "srv-a", "network_binding_ref": "inst.vlan.a"}
    rows[2]["extensions"] = {"ip_allocations": [{"host_os_ref": "inst.os.a"}]}  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7844" for diag in result.diagnostics)


def test_network_runtime_reachability_validator_accepts_active_only_host_os_reachability():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[0]["os_refs"] = ["inst.os.a", "inst.os.b"]  # type: ignore[index]
    rows.insert(2, {"group": "os", "instance": "inst.os.b", "class_ref": "class.os", "layer": "L1", "status": "mapped"})
    rows[3]["extensions"] = {"ip_allocations": [{"host_os_ref": "inst.os.a"}, {"host_os_ref": "inst.os.b"}]}  # type: ignore[index]
    rows[-1]["runtime"] = {"type": "docker", "target_ref": "srv-a", "network_binding_ref": "inst.vlan.a"}
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_runtime_reachability_validator_supports_non_vlan_legacy_network_shape():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[2]["class_ref"] = "class.network.segment"  # type: ignore[index]
    rows[2].pop("layer")  # type: ignore[index]
    rows[2].pop("extensions")  # type: ignore[index]
    rows[2]["ip_allocations"] = [{"device_ref": "srv-a", "host_os_ref": "inst.os.a"}]  # type: ignore[index]
    rows[3].pop("extensions")  # type: ignore[index]
    rows[3]["network"] = {"vlan_ref": "inst.vlan.a"}  # type: ignore[index]
    rows[-1]["runtime"] = {"type": "docker", "target_ref": "srv-a", "network_binding_ref": "inst.vlan.a"}
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_runtime_reachability_validator_accepts_docker_runtime_to_l4_docker_with_network():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[3] = {  # type: ignore[index]
        "group": "docker",
        "instance": "docker-a",
        "class_ref": "class.compute.workload.docker",
        "layer": "L4",
        "extensions": {"networks": [{"network_ref": "inst.vlan.a"}]},
    }
    rows[-1]["runtime"] = {"type": "docker", "target_ref": "docker-a", "network_binding_ref": "inst.vlan.a"}  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_runtime_reachability_validator_execute_stage_requires_committed_normalized_rows(
    tmp_path: Path,
) -> None:
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

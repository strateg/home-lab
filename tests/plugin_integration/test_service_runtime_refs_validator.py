#!/usr/bin/env python3
"""Integration tests for service runtime refs validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.service_runtime_refs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


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
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()


def _valid_rows() -> list[dict]:
    return [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
        {"group": "lxc", "instance": "lxc-a", "class_ref": "class.compute.workload.container", "layer": "L4"},
        {
            "group": "os",
            "instance": "os-a",
            "class_ref": "class.os",
            "layer": "L1",
            "status": "active",
            "extensions": {"capabilities": ["docker"], "host_type": "baremetal"},
        },
        {"group": "devices", "instance": "srv-b", "class_ref": "class.router", "layer": "L1", "os_refs": ["os-a"]},
        {"group": "network", "instance": "inst.vlan.a", "class_ref": "class.network.vlan", "layer": "L2"},
        {
            "group": "services",
            "instance": "svc-a",
            "class_ref": "class.service.monitoring",
            "layer": "L5",
            "runtime": {"type": "lxc", "target_ref": "lxc-a", "network_binding_ref": "inst.vlan.a"},
        },
    ]


def test_service_runtime_refs_validator_accepts_valid_runtime_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _valid_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_service_runtime_refs_validator_rejects_unknown_target_ref():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[-1]["runtime"]["target_ref"] = "missing"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7841" for diag in result.diagnostics)


def test_service_runtime_refs_validator_rejects_wrong_runtime_target_type():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[-1]["runtime"]["type"] = "docker"  # type: ignore[index]
    rows[-1]["runtime"]["target_ref"] = "lxc-a"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7841" for diag in result.diagnostics)


def test_service_runtime_refs_validator_warns_on_unknown_runtime_type():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[-1]["runtime"]["type"] = "custom"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7842" for diag in result.diagnostics)


def test_service_runtime_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7841" for diag in result.diagnostics)


def test_service_runtime_refs_validator_warns_on_legacy_runtime_fields():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[-1]["container"] = True  # type: ignore[index]
    rows[-1]["config"] = {"docker": {"host_ip": "10.0.0.2"}}  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status in {PluginStatus.PARTIAL, PluginStatus.SUCCESS}
    assert any(diag.code == "W7845" for diag in result.diagnostics)


def test_service_runtime_refs_validator_warns_on_runtime_with_legacy_refs():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[-1]["device_ref"] = "srv-b"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7845" for diag in result.diagnostics)


def test_service_runtime_refs_validator_warns_on_legacy_external_services_payload():
    registry = _registry()
    ctx = _context()
    ctx.raw_yaml = {"L5_application": {"external_services": [{"id": "legacy-ext"}]}}
    _publish_rows(ctx, [])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any("external_services is deprecated" in diag.message for diag in result.diagnostics)


def test_service_runtime_refs_validator_rejects_docker_runtime_without_container_capability():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[2]["extensions"] = {"capabilities": ["vm"], "host_type": "baremetal"}  # type: ignore[index]
    rows[-1]["runtime"] = {"type": "docker", "target_ref": "srv-b", "network_binding_ref": "inst.vlan.a"}  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7841" for diag in result.diagnostics)


def test_service_runtime_refs_validator_rejects_baremetal_runtime_with_invalid_host_type():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[2]["extensions"] = {"capabilities": ["container"], "host_type": "cloud"}  # type: ignore[index]
    rows[-1]["runtime"] = {"type": "baremetal", "target_ref": "srv-b", "network_binding_ref": "inst.vlan.a"}  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7841" for diag in result.diagnostics)


def test_service_runtime_refs_validator_accepts_mapped_host_os_status_for_device_runtime():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[2]["status"] = "mapped"  # type: ignore[index]
    rows[-1]["runtime"] = {"type": "docker", "target_ref": "srv-b", "network_binding_ref": "inst.vlan.a"}  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert not any("has no active host OS entry" in diag.message for diag in result.diagnostics)


def test_service_runtime_refs_validator_skips_runtime_capability_checks_when_host_os_metadata_not_declared():
    registry = _registry()
    ctx = _context()
    rows = _valid_rows()
    rows[2]["extensions"] = {}  # type: ignore[index]
    rows[-1]["runtime"] = {"type": "docker", "target_ref": "srv-b", "network_binding_ref": "inst.vlan.a"}  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert not any("runtime type docker requires host capability" in diag.message for diag in result.diagnostics)

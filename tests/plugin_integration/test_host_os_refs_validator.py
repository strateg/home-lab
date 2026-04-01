#!/usr/bin/env python3
"""Integration tests for host_os refs validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.host_os_refs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context(*, objects: dict | None = None) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects=objects or {},
        instance_bindings={"instance_bindings": {}},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()


def test_host_os_refs_validator_accepts_runtime_target_with_active_os_binding():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "devices",
                "instance": "srv-a",
                "class_ref": "class.router",
                "layer": "L1",
                "os_refs": ["inst.os.a"],
            },
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os", "layer": "L1", "status": "mapped"},
            {
                "group": "services",
                "instance": "svc-a",
                "class_ref": "class.service.web_ui",
                "layer": "L5",
                "runtime": {"type": "docker", "target_ref": "srv-a"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_host_os_refs_validator_rejects_runtime_target_without_active_os_binding():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1", "os_refs": []},
            {
                "group": "devices",
                "instance": "srv-b",
                "class_ref": "class.router",
                "layer": "L1",
                "os_refs": ["inst.os.b"],
            },
            {"group": "os", "instance": "inst.os.b", "class_ref": "class.os", "layer": "L1", "status": "active"},
            {
                "group": "services",
                "instance": "svc-a",
                "class_ref": "class.service.web_ui",
                "layer": "L5",
                "runtime": {"type": "docker", "target_ref": "srv-a"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7892" for diag in result.diagnostics)


def test_host_os_refs_validator_rejects_workload_device_without_active_os_binding():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1", "os_refs": []},
            {"group": "os", "instance": "inst.os.a", "class_ref": "class.os", "layer": "L1", "status": "mapped"},
            {
                "group": "vms",
                "instance": "vm-a",
                "class_ref": "class.compute.cloud_vm",
                "layer": "L4",
                "extensions": {"device_ref": "srv-a"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7892" for diag in result.diagnostics)


def test_host_os_refs_validator_skips_check_when_host_os_inventory_absent():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1", "os_refs": []},
            {
                "group": "services",
                "instance": "svc-a",
                "class_ref": "class.service.web_ui",
                "layer": "L5",
                "runtime": {"type": "docker", "target_ref": "srv-a"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_host_os_refs_validator_rejects_architecture_mismatch_between_os_and_device():
    registry = _registry()
    ctx = _context(
        objects={
            "obj.device.arm64": {"object": "obj.device.arm64", "hardware_specs": {"cpu": {"architecture": "arm64"}}},
            "obj.os.x86_64": {
                "object": "obj.os.x86_64",
                "class_ref": "class.os",
                "properties": {"architecture": "x86_64"},
            },
        }
    )
    _publish_rows(
        ctx,
        [
            {
                "group": "devices",
                "instance": "srv-a",
                "class_ref": "class.router",
                "layer": "L1",
                "object_ref": "obj.device.arm64",
                "os_refs": ["inst.os.a"],
            },
            {
                "group": "os",
                "instance": "inst.os.a",
                "class_ref": "class.os",
                "layer": "L1",
                "object_ref": "obj.os.x86_64",
                "status": "mapped",
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7891" for diag in result.diagnostics)


def test_host_os_refs_validator_rejects_root_storage_endpoint_on_other_device():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "devices",
                "instance": "srv-a",
                "class_ref": "class.router",
                "layer": "L1",
                "os_refs": ["inst.os.a"],
            },
            {"group": "devices", "instance": "srv-b", "class_ref": "class.router", "layer": "L1", "os_refs": []},
            {
                "group": "os",
                "instance": "inst.os.a",
                "class_ref": "class.os",
                "layer": "L1",
                "status": "mapped",
                "extensions": {"installation": {"root_storage_endpoint_ref": "endpoint-a"}},
            },
            {
                "group": "data-assets",
                "instance": "endpoint-a",
                "class_ref": "class.storage.storage_endpoint",
                "layer": "L3",
                "extensions": {"mount_point_ref": "mount-a"},
            },
            {
                "group": "data-assets",
                "instance": "mount-a",
                "class_ref": "class.storage.mount_point",
                "layer": "L3",
                "extensions": {"device_ref": "srv-b"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7893" for diag in result.diagnostics)


def test_host_os_refs_validator_requires_installation_for_baremetal_host_type():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "devices",
                "instance": "srv-a",
                "class_ref": "class.router",
                "layer": "L1",
                "os_refs": ["inst.os.a"],
            },
            {
                "group": "os",
                "instance": "inst.os.a",
                "class_ref": "class.os",
                "layer": "L1",
                "status": "mapped",
                "extensions": {"host_type": "baremetal"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7894" for diag in result.diagnostics)


def test_host_os_refs_validator_rejects_non_canonical_architecture_extension_value():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "devices",
                "instance": "srv-a",
                "class_ref": "class.router",
                "layer": "L1",
                "os_refs": ["inst.os.a"],
            },
            {
                "group": "os",
                "instance": "inst.os.a",
                "class_ref": "class.os",
                "layer": "L1",
                "extensions": {"architecture": "amd64"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7895" for diag in result.diagnostics)


def test_host_os_refs_validator_rejects_non_canonical_architecture_top_level_value():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "devices",
                "instance": "srv-a",
                "class_ref": "class.router",
                "layer": "L1",
                "os_refs": ["inst.os.a"],
            },
            {
                "group": "os",
                "instance": "inst.os.a",
                "class_ref": "class.os",
                "layer": "L1",
                "architecture": "amd64",
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7895" for diag in result.diagnostics)


def test_host_os_refs_validator_rejects_unsupported_architecture_extension_value():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "devices",
                "instance": "srv-a",
                "class_ref": "class.router",
                "layer": "L1",
                "os_refs": ["inst.os.a"],
            },
            {
                "group": "os",
                "instance": "inst.os.a",
                "class_ref": "class.os",
                "layer": "L1",
                "extensions": {"architecture": "mipsel"},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7895" for diag in result.diagnostics)


def test_host_os_refs_validator_rejects_capability_not_allowed_for_host_type():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "devices",
                "instance": "srv-a",
                "class_ref": "class.router",
                "layer": "L1",
                "os_refs": ["inst.os.a"],
            },
            {
                "group": "os",
                "instance": "inst.os.a",
                "class_ref": "class.os",
                "layer": "L1",
                "extensions": {"host_type": "embedded", "capabilities": ["vm"]},
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7896" for diag in result.diagnostics)


def test_host_os_refs_validator_rejects_capability_not_allowed_for_top_level_host_type():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "devices",
                "instance": "srv-a",
                "class_ref": "class.router",
                "layer": "L1",
                "os_refs": ["inst.os.a"],
            },
            {
                "group": "os",
                "instance": "inst.os.a",
                "class_ref": "class.os",
                "layer": "L1",
                "host_type": "embedded",
                "capabilities": ["vm"],
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7896" for diag in result.diagnostics)


def test_host_os_refs_validator_reads_workload_device_ref_from_top_level():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1", "os_refs": []},
            {"group": "os", "instance": "inst.os.b", "class_ref": "class.os", "layer": "L1", "status": "active"},
            {
                "group": "vms",
                "instance": "vm-a",
                "class_ref": "class.compute.cloud_vm",
                "layer": "L4",
                "device_ref": "srv-a",
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7892" for diag in result.diagnostics)


def test_host_os_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7890" for diag in result.diagnostics)

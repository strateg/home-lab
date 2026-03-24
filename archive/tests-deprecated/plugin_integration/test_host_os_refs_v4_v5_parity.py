#!/usr/bin/env python3
"""Side-by-side parity checks for v4/v5 host OS runtime target semantics."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry
from kernel.plugin_base import Stage

V4_REFERENCES_CHECKS = (
    Path(__file__).resolve().parents[3]
    / "v4"
    / "topology-tools"
    / "scripts"
    / "validators"
    / "checks"
    / "references.py"
)
V5_HOST_OS_PLUGIN_ID = "base.validator.host_os_refs"


def _load_v4_references_checks_module() -> Any:
    spec = importlib.util.spec_from_file_location("v4_references_checks", V4_REFERENCES_CHECKS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load v4 references checks module from {V4_REFERENCES_CHECKS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_runtime_target_without_host_os_binding_is_error_in_v4_and_v5():
    v4_module = _load_v4_references_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_host_os_refs(
        topology={
            "L1_foundation": {"devices": [{"id": "srv-a"}, {"id": "srv-b"}]},
            "L4_platform": {"host_operating_systems": [{"id": "hos-b", "device_ref": "srv-b", "status": "active"}]},
            "L5_application": {"services": [{"id": "svc-a", "runtime": {"type": "docker", "target_ref": "srv-a"}}]},
        },
        ids={
            "devices": {"srv-a", "srv-b"},
            "storage_endpoints": set(),
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any(
        "active runtime target requires at least one active host_operating_systems entry" in message
        for message in v4_errors
    )

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
            {"group": "os", "instance": "inst.os.b", "class_ref": "class.os", "layer": "L1", "status": "mapped"},
            {
                "group": "services",
                "instance": "svc-a",
                "class_ref": "class.service.web_ui",
                "layer": "L5",
                "runtime": {"type": "docker", "target_ref": "srv-a"},
            },
        ],
    )
    result = registry.execute_plugin(V5_HOST_OS_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7892" for diag in result.diagnostics)


def test_host_os_architecture_mismatch_is_error_in_v4_and_v5():
    v4_module = _load_v4_references_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_host_os_refs(
        topology={
            "L1_foundation": {
                "devices": [{"id": "srv-a", "specs": {"cpu": {"architecture": "arm64"}}}],
            },
            "L3_data": {"storage_endpoints": [], "mount_points": []},
            "L4_platform": {
                "host_operating_systems": [{"id": "hos-a", "device_ref": "srv-a", "architecture": "x86_64"}]
            },
        },
        ids={
            "devices": {"srv-a"},
            "storage_endpoints": set(),
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("does not match device 'srv-a' architecture" in message for message in v4_errors)

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
            },
        ],
    )
    result = registry.execute_plugin(V5_HOST_OS_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7891" for diag in result.diagnostics)


def test_host_os_root_storage_mount_device_mismatch_is_error_in_v4_and_v5():
    v4_module = _load_v4_references_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_host_os_refs(
        topology={
            "L1_foundation": {"devices": [{"id": "srv-a"}, {"id": "srv-b"}]},
            "L3_data": {
                "storage_endpoints": [{"id": "endpoint-a", "mount_point_ref": "mount-a"}],
                "mount_points": [{"id": "mount-a", "device_ref": "srv-b"}],
            },
            "L4_platform": {
                "host_operating_systems": [
                    {
                        "id": "hos-a",
                        "device_ref": "srv-a",
                        "installation": {"root_storage_endpoint_ref": "endpoint-a"},
                    }
                ]
            },
        },
        ids={
            "devices": {"srv-a", "srv-b"},
            "storage_endpoints": {"endpoint-a"},
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("points to mount point on device 'srv-b', expected 'srv-a'" in message for message in v4_errors)

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
                "extensions": {"installation": {"root_storage_endpoint_ref": "endpoint-a"}},
            },
            {
                "group": "storage",
                "instance": "endpoint-a",
                "class_ref": "class.storage.storage_endpoint",
                "layer": "L3",
                "extensions": {"mount_point_ref": "mount-a"},
            },
            {
                "group": "storage",
                "instance": "mount-a",
                "class_ref": "class.storage.mount_point",
                "layer": "L3",
                "extensions": {"device_ref": "srv-b"},
            },
        ],
    )
    result = registry.execute_plugin(V5_HOST_OS_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7893" for diag in result.diagnostics)


def test_host_os_non_canonical_architecture_is_error_in_v4_and_v5():
    v4_module = _load_v4_references_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_host_os_refs(
        topology={
            "L1_foundation": {"devices": [{"id": "srv-a", "specs": {"cpu": {"architecture": "x86_64"}}}]},
            "L3_data": {"storage_endpoints": [], "mount_points": []},
            "L4_platform": {
                "host_operating_systems": [{"id": "hos-a", "device_ref": "srv-a", "architecture": "amd64"}]
            },
        },
        ids={
            "devices": {"srv-a"},
            "storage_endpoints": set(),
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("must be canonical; use 'x86_64'" in message for message in v4_errors)

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
    result = registry.execute_plugin(V5_HOST_OS_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7895" for diag in result.diagnostics)


def test_host_os_capability_host_type_mismatch_is_error_in_v4_and_v5():
    v4_module = _load_v4_references_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_host_os_refs(
        topology={
            "L1_foundation": {"devices": [{"id": "srv-a", "specs": {"cpu": {"architecture": "x86_64"}}}]},
            "L3_data": {"storage_endpoints": [], "mount_points": []},
            "L4_platform": {
                "host_operating_systems": [
                    {
                        "id": "hos-a",
                        "device_ref": "srv-a",
                        "architecture": "x86_64",
                        "host_type": "embedded",
                        "capabilities": ["vm"],
                    }
                ]
            },
        },
        ids={
            "devices": {"srv-a"},
            "storage_endpoints": set(),
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("capability 'vm' is not valid for host_type 'embedded'" in message for message in v4_errors)

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
    result = registry.execute_plugin(V5_HOST_OS_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7896" for diag in result.diagnostics)


def test_host_os_top_level_architecture_is_validated_in_v4_and_v5():
    v4_module = _load_v4_references_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_host_os_refs(
        topology={
            "L1_foundation": {"devices": [{"id": "srv-a", "specs": {"cpu": {"architecture": "x86_64"}}}]},
            "L3_data": {"storage_endpoints": [], "mount_points": []},
            "L4_platform": {
                "host_operating_systems": [{"id": "hos-a", "device_ref": "srv-a", "architecture": "amd64"}]
            },
        },
        ids={
            "devices": {"srv-a"},
            "storage_endpoints": set(),
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("must be canonical; use 'x86_64'" in message for message in v4_errors)

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
    result = registry.execute_plugin(V5_HOST_OS_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7895" for diag in result.diagnostics)


def test_host_os_top_level_capability_host_type_mismatch_is_error_in_v4_and_v5():
    v4_module = _load_v4_references_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_host_os_refs(
        topology={
            "L1_foundation": {"devices": [{"id": "srv-a", "specs": {"cpu": {"architecture": "x86_64"}}}]},
            "L3_data": {"storage_endpoints": [], "mount_points": []},
            "L4_platform": {
                "host_operating_systems": [
                    {
                        "id": "hos-a",
                        "device_ref": "srv-a",
                        "architecture": "x86_64",
                        "host_type": "embedded",
                        "capabilities": ["vm"],
                    }
                ]
            },
        },
        ids={
            "devices": {"srv-a"},
            "storage_endpoints": set(),
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("capability 'vm' is not valid for host_type 'embedded'" in message for message in v4_errors)

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
    result = registry.execute_plugin(V5_HOST_OS_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7896" for diag in result.diagnostics)

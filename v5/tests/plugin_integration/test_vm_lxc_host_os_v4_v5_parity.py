#!/usr/bin/env python3
"""Side-by-side parity checks for VM/LXC host_os binding semantics."""

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
    Path(__file__).resolve().parents[3] / "v4" / "topology-tools" / "scripts" / "validators" / "checks" / "references.py"
)
V5_VM_PLUGIN_ID = "base.validator.vm_refs"
V5_LXC_PLUGIN_ID = "base.validator.lxc_refs"


def _load_v4_references_checks_module() -> Any:
    spec = importlib.util.spec_from_file_location("v4_references_checks_vm_lxc", V4_REFERENCES_CHECKS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load v4 references checks module from {V4_REFERENCES_CHECKS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context() -> PluginContext:
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
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


def test_vm_requires_host_os_ref_on_multi_active_bindings_in_v4_and_v5():
    v4_module = _load_v4_references_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_vm_refs(
        topology={
            "L4_platform": {
                "host_operating_systems": [
                    {"id": "hos-a", "device_ref": "srv-a", "status": "active"},
                    {"id": "hos-b", "device_ref": "srv-a", "status": "active"},
                ],
                "templates": {"vms": []},
                "vms": [{"id": "vm-a", "device_ref": "srv-a"}],
            }
        },
        ids={
            "devices": {"srv-a"},
            "trust_zones": set(),
            "templates": set(),
            "host_operating_systems": {"hos-a", "hos-b"},
            "storage": set(),
            "bridges": set(),
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("multiple active host OS objects; host_os_ref is required" in message for message in v4_errors)

    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1", "os_refs": ["os-a", "os-b"]},
            {"group": "os", "instance": "os-a", "class_ref": "class.os", "layer": "L1", "status": "active"},
            {"group": "os", "instance": "os-b", "class_ref": "class.os", "layer": "L1", "status": "active"},
            {
                "group": "vms",
                "instance": "vm-a",
                "class_ref": "class.compute.cloud_vm",
                "layer": "L4",
                "extensions": {"device_ref": "srv-a"},
            },
        ],
    )
    result = registry.execute_plugin(V5_VM_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7873" for diag in result.diagnostics)


def test_lxc_requires_host_os_ref_on_multi_active_bindings_in_v4_and_v5():
    v4_module = _load_v4_references_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_lxc_refs(
        topology={
            "L4_platform": {
                "host_operating_systems": [
                    {"id": "hos-a", "device_ref": "srv-a", "status": "active"},
                    {"id": "hos-b", "device_ref": "srv-a", "status": "active"},
                ],
                "templates": {"lxc": []},
                "lxc": [{"id": "lxc-a", "device_ref": "srv-a", "storage": {}}],
            }
        },
        ids={
            "devices": {"srv-a"},
            "trust_zones": set(),
            "templates": set(),
            "host_operating_systems": {"hos-a", "hos-b"},
            "storage": set(),
            "resource_profiles": set(),
            "data_assets": set(),
            "bridges": set(),
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("multiple active host OS objects; host_os_ref is required" in message for message in v4_errors)

    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1", "os_refs": ["os-a", "os-b"]},
            {"group": "os", "instance": "os-a", "class_ref": "class.os", "layer": "L1", "status": "active"},
            {"group": "os", "instance": "os-b", "class_ref": "class.os", "layer": "L1", "status": "active"},
            {
                "group": "lxc",
                "instance": "lxc-a",
                "class_ref": "class.compute.workload.container",
                "layer": "L4",
                "extensions": {"device_ref": "srv-a", "storage": {}},
            },
        ],
    )
    result = registry.execute_plugin(V5_LXC_PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7883" for diag in result.diagnostics)

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
    Path(__file__).resolve().parents[3] / "v4" / "topology-tools" / "scripts" / "validators" / "checks" / "references.py"
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
    assert any("active runtime target requires at least one active host_operating_systems entry" in message for message in v4_errors)

    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1", "os_refs": []},
            {"group": "devices", "instance": "srv-b", "class_ref": "class.router", "layer": "L1", "os_refs": ["inst.os.b"]},
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

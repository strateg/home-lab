#!/usr/bin/env python3
"""Side-by-side error parity checks for v4 and v5 service reference semantics."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.service_dependency_refs"
V4_REFS_CHECKS = (
    Path(__file__).resolve().parents[3] / "v4" / "topology-tools" / "scripts" / "validators" / "checks" / "references.py"
)


def _load_v4_reference_checks_module() -> Any:
    spec = importlib.util.spec_from_file_location("v4_reference_checks", V4_REFS_CHECKS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load v4 reference checks module from {V4_REFS_CHECKS}")
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


def test_service_data_asset_ref_missing_is_error_in_v4_and_v5():
    v4_module = _load_v4_reference_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_service_refs(
        topology={
            "L5_application": {
                "services": [
                    {
                        "id": "svc-a",
                        "data_asset_refs": ["asset.missing"],
                    }
                ]
            }
        },
        ids={
            "devices": set(),
            "vms": set(),
            "lxc": set(),
            "networks": set(),
            "trust_zones": set(),
            "data_assets": set(),
            "services": {"svc-a"},
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("data_asset_ref 'asset.missing'" in message for message in v4_errors)

    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "services",
                "instance": "svc-a",
                "class_ref": "class.service.web_ui",
                "layer": "L5",
                "extensions": {"data_asset_refs": ["asset.missing"]},
            }
        ],
    )
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7849" for diag in result.diagnostics)


def test_service_dependency_ref_missing_is_error_in_v4_and_v5():
    v4_module = _load_v4_reference_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_service_refs(
        topology={
            "L5_application": {
                "services": [
                    {
                        "id": "svc-a",
                        "dependencies": [{"service_ref": "svc-missing"}],
                    }
                ]
            }
        },
        ids={
            "devices": set(),
            "vms": set(),
            "lxc": set(),
            "networks": set(),
            "trust_zones": set(),
            "data_assets": set(),
            "services": {"svc-a"},
        },
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("dependency service_ref 'svc-missing'" in message for message in v4_errors)

    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"group": "services", "instance": "svc-a", "class_ref": "class.service.web_ui", "layer": "L5"},
            {
                "group": "services",
                "instance": "svc-b",
                "class_ref": "class.service.web_ui",
                "layer": "L5",
                "extensions": {"dependencies": [{"service_ref": "svc-missing"}]},
            },
        ],
    )
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert any(diag.code == "E7850" for diag in result.diagnostics)

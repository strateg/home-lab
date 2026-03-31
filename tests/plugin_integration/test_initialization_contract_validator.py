#!/usr/bin/env python3
"""Integration tests for initialization contract validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.initialization_contract"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context(objects: dict[str, dict]) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )


def test_initialization_contract_validator_allows_missing_contract_for_compute_object() -> None:
    registry = _registry()
    ctx = _context(
        objects={
            "obj.compute.demo": {
                "object": "obj.compute.demo",
                "class_ref": "class.compute.edge_node",
            }
        }
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_initialization_contract_validator_rejects_non_object_contract() -> None:
    registry = _registry()
    ctx = _context(
        objects={
            "obj.router.bad": {
                "object": "obj.router.bad",
                "class_ref": "class.router",
                "initialization_contract": "not-a-mapping",
            }
        }
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9701" for diag in result.diagnostics)


def test_initialization_contract_validator_rejects_schema_violations() -> None:
    registry = _registry()
    ctx = _context(
        objects={
            "obj.router.bad": {
                "object": "obj.router.bad",
                "class_ref": "class.router",
                "initialization_contract": {
                    "version": "1.0.0",
                    "mechanism": "unknown",
                },
            }
        }
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9702" for diag in result.diagnostics)


def test_initialization_contract_validator_accepts_valid_contract() -> None:
    registry = _registry()
    ctx = _context(
        objects={
            "obj.router.good": {
                "object": "obj.router.good",
                "class_ref": "class.router",
                "initialization_contract": {
                    "version": "1.0.0",
                    "mechanism": "netinstall",
                    "bootstrap": {"template": "bootstrap/mikrotik/init.rsc.j2"},
                    "handover": {"checks": [{"type": "api_reachable"}]},
                },
            }
        }
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_initialization_contract_validator_ignores_non_target_class() -> None:
    registry = _registry()
    ctx = _context(
        objects={
            "obj.service.demo": {
                "object": "obj.service.demo",
                "class_ref": "class.service.proxy",
                "initialization_contract": {
                    "version": "1.0.0",
                    "mechanism": "unknown",
                },
            }
        }
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []

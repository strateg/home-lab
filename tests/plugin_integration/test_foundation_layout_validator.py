#!/usr/bin/env python3
"""Integration tests for foundation layout validator plugin."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.foundation_layout"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _manifest_template() -> dict:
    return {
        "version": "5.0.0",
        "model": "class-object-instance",
        "framework": {
            "class_modules_root": "topology/class-modules",
            "object_modules_root": "topology/object-modules",
        },
        "project": {"active": "home-lab", "projects_root": "projects"},
        "meta": {"instance": "home-lab", "status": "migration"},
    }


def _context(raw_yaml: dict) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml=copy.deepcopy(raw_yaml),
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        config={"repo_root": str(Path(__file__).resolve().parents[2])},
    )


def test_foundation_layout_validator_accepts_repository_layout():
    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(_manifest_template()), Stage.VALIDATE)

    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_foundation_layout_validator_rejects_missing_root_path():
    registry = _registry()
    manifest = _manifest_template()
    manifest["framework"]["class_modules_root"] = "topology/class-modules-missing"

    result = registry.execute_plugin(PLUGIN_ID, _context(manifest), Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7812" for diag in result.diagnostics)


def test_foundation_layout_validator_rejects_empty_root_directory(tmp_path: Path):
    registry = _registry()
    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    class_root.mkdir()
    object_root.mkdir()

    manifest = _manifest_template()
    manifest["framework"]["class_modules_root"] = str(class_root)
    manifest["framework"]["object_modules_root"] = str(object_root)

    result = registry.execute_plugin(PLUGIN_ID, _context(manifest), Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    codes = [diag.code for diag in result.diagnostics]
    assert "E7813" in codes

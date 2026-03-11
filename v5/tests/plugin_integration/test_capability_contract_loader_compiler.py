#!/usr/bin/env python3
"""Integration tests for capability contract loader compiler plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.compiler.capability_contract_loader"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def test_capability_contract_loader_skips_when_core_owner():
    registry = _registry()
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"compilation_owner_capability_contract_data": "core"},
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS
    assert result.output_data["catalog_ids"] == []


def test_capability_contract_loader_plugin_owner_loads_contract(tmp_path):
    registry = _registry()
    catalog = tmp_path / "catalog.yaml"
    packs = tmp_path / "packs.yaml"
    catalog.write_text(
        "capabilities:\n" "  - id: cap.a\n" "  - id: cap.b\n",
        encoding="utf-8",
    )
    packs.write_text(
        "packs:\n" "  - id: pack.a\n" "    capabilities: [cap.a]\n",
        encoding="utf-8",
    )

    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={
            "compilation_owner_capability_contract_data": "plugin",
            "capability_catalog_path": str(catalog),
            "capability_packs_path": str(packs),
        },
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS
    assert result.output_data["catalog_ids"] == ["cap.a", "cap.b"]
    assert "pack.a" in result.output_data["packs_map"]

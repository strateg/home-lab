#!/usr/bin/env python3
"""Thin facade smoke tests for the v5 plugin registry (ADR 0063).

S9 of docs/analysis/PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07.md:
the original 2494-line module was split into tests/kernel/registry/
and tests/kernel/scheduler/ (calls stay facade-level). This file
keeps only real-manifest smoke coverage of the PluginRegistry
facade surface: manifest loading, plugin loading, execution order,
stats and kernel info.
"""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[1] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import (  # noqa: E402
    KERNEL_API_VERSION,
    KERNEL_VERSION,
    PluginKind,
    PluginRegistry,
)
from kernel.plugin_base import Stage  # noqa: E402


def test_manifest_loading():
    """Test loading plugin manifest from YAML (supports sharded manifests with includes)."""
    manifest_path = V5_TOOLS / "plugins" / "plugins.yaml"
    # Use registry to load manifest with includes support (sharded manifests)
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest_path)

    assert len(registry.specs) >= 1

    # Test discoverer plugin
    discover_plugin = registry.specs.get("base.discover.inventory")
    assert discover_plugin is not None
    assert discover_plugin.kind == PluginKind.DISCOVERER
    assert Stage.DISCOVER in discover_plugin.stages
    assert discover_plugin.timeout == 30

    # Find the reference validator plugin
    ref_plugin = registry.specs.get("base.validator.references")
    assert ref_plugin is not None
    assert ref_plugin.kind == PluginKind.VALIDATOR_JSON
    assert Stage.VALIDATE in ref_plugin.stages
    assert ref_plugin.config == {"strict_mode": False}
    print("PASS: Manifest loading works")


def test_registry_load():
    """Test registry loading plugins."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    assert len(registry.specs) >= 1
    assert "base.validator.references" in registry.specs
    assert len(registry.get_load_errors()) == 0
    print("PASS: Registry loading works")


def test_execution_order():
    """Test plugin execution order resolution."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    order = registry.get_execution_order(Stage.VALIDATE)
    assert "base.validator.references" in order
    print("PASS: Execution order works")


def test_plugin_instantiation():
    """Test loading and instantiating a plugin."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    plugin = registry.load_plugin("base.validator.references")
    assert plugin.plugin_id == "base.validator.references"
    assert plugin.kind == PluginKind.VALIDATOR_JSON
    assert plugin.api_version == "1.x"
    print("PASS: Plugin instantiation works")


def test_registry_stats():
    """Test registry statistics."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    stats = registry.get_stats()
    assert stats["loaded"] >= 1
    assert "validator_json" in stats["by_kind"]
    print("PASS: Registry stats work")


def test_kernel_info():
    """Test kernel info retrieval."""
    info = PluginRegistry.get_kernel_info()
    assert info["version"] == KERNEL_VERSION
    assert info["plugin_api_version"] == KERNEL_API_VERSION
    assert "1.x" in info["supported_api_versions"]
    assert info["default_timeout"] == 30.0
    print("PASS: Kernel info works")

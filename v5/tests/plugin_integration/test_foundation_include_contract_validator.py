#!/usr/bin/env python3
"""Integration tests for foundation include contract validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.foundation_include_contract"

REQUIRED_DIRS = (
    "topology/instances/L0-meta/meta",
    "topology/instances/L1-foundation/devices",
    "topology/instances/L1-foundation/firmware",
    "topology/instances/L1-foundation/os",
    "topology/instances/L1-foundation/physical-links",
    "topology/instances/L1-foundation/power",
    "topology/instances/L2-network/data-channels",
    "topology/instances/L2-network/network",
    "topology/instances/L3-data/storage",
    "topology/instances/L4-platform/lxc",
    "topology/instances/L4-platform/vms",
    "topology/instances/L5-application/services",
    "topology/instances/L6-observability/observability",
    "topology/instances/L7-operations/operations",
)


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context(project_root: str | None) -> PluginContext:
    config = {}
    if project_root is not None:
        config["project_root"] = project_root
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        config=config,
    )


def _build_tree(root: Path) -> None:
    for rel in REQUIRED_DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)


def test_foundation_include_contract_validator_accepts_valid_tree(tmp_path: Path):
    _build_tree(tmp_path)
    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(str(tmp_path)), Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_foundation_include_contract_validator_rejects_missing_required_dir(tmp_path: Path):
    _build_tree(tmp_path)
    missing_dir = tmp_path / "topology" / "instances" / "L3-data" / "storage"
    missing_dir.rmdir()

    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(str(tmp_path)), Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7846" for diag in result.diagnostics)


def test_foundation_include_contract_validator_rejects_manual_index_file(tmp_path: Path):
    _build_tree(tmp_path)
    index_file = tmp_path / "topology" / "instances" / "L1-foundation" / "devices" / "_index.yaml"
    index_file.write_text("{}", encoding="utf-8")

    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(str(tmp_path)), Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7847" for diag in result.diagnostics)


def test_foundation_include_contract_validator_requires_project_root():
    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(None), Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7845" for diag in result.diagnostics)

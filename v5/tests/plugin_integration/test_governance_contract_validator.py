#!/usr/bin/env python3
"""Integration tests for v5 governance contract validator plugin."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.governance_contract"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _valid_manifest() -> dict:
    return {
        "version": "5.0.0",
        "model": "class-object-instance",
        "meta": {"instance": "home-lab", "status": "migration"},
        "framework": {
            "class_modules_root": "v5/topology/class-modules",
            "object_modules_root": "v5/topology/object-modules",
            "model_lock": "v5/topology/model.lock.yaml",
            "layer_contract": "v5/topology/layer-contract.yaml",
            "capability_catalog": "v5/topology/class-modules/router/capability-catalog.yaml",
            "capability_packs": "v5/topology/class-modules/router/capability-packs.yaml",
        },
        "project": {"active": "home-lab", "projects_root": "v5/projects"},
    }


def _context(raw_yaml: dict) -> PluginContext:
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml=copy.deepcopy(raw_yaml),
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )


def test_governance_contract_validator_accepts_valid_manifest():
    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(_valid_manifest()), Stage.VALIDATE)

    assert result.status == PluginStatus.SUCCESS
    assert not result.has_errors
    assert result.diagnostics == []


def test_governance_contract_validator_rejects_invalid_version():
    registry = _registry()
    manifest = _valid_manifest()
    manifest["version"] = "4.9.0"

    result = registry.execute_plugin(PLUGIN_ID, _context(manifest), Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7801" for diag in result.diagnostics)


def test_governance_contract_validator_rejects_missing_framework_key():
    registry = _registry()
    manifest = _valid_manifest()
    manifest["framework"].pop("layer_contract")

    result = registry.execute_plugin(PLUGIN_ID, _context(manifest), Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7803" for diag in result.diagnostics)


def test_governance_contract_validator_warns_on_meta_project_mismatch():
    registry = _registry()
    manifest = _valid_manifest()
    manifest["meta"]["instance"] = "other-project"

    result = registry.execute_plugin(PLUGIN_ID, _context(manifest), Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "E7806" for diag in result.diagnostics)

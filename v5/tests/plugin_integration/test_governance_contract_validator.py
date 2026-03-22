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


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()


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


def test_governance_contract_validator_rejects_metadata_date_order():
    registry = _registry()
    manifest = _valid_manifest()
    manifest["meta"]["metadata"] = {
        "created": "2026-03-22",
        "last_updated": "2026-03-01",
    }

    result = registry.execute_plugin(PLUGIN_ID, _context(manifest), Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7808" for diag in result.diagnostics)


def test_governance_contract_validator_warns_on_changelog_version_gap():
    registry = _registry()
    manifest = _valid_manifest()
    manifest["meta"]["metadata"] = {
        "created": "2026-03-01",
        "last_updated": "2026-03-22",
        "changelog": [{"version": "5.0.1", "note": "next release"}],
    }

    result = registry.execute_plugin(PLUGIN_ID, _context(manifest), Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7810" for diag in result.diagnostics)


def test_governance_contract_validator_rejects_unknown_default_security_policy_ref():
    registry = _registry()
    manifest = _valid_manifest()
    manifest["meta"]["defaults"] = {"refs": {"security_policy_ref": "fw-missing"}}
    ctx = _context(manifest)
    _publish_rows(ctx, [])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7811" for diag in result.diagnostics)


def test_governance_contract_validator_rejects_network_manager_ref_outside_l1():
    registry = _registry()
    manifest = _valid_manifest()
    manifest["meta"]["defaults"] = {"refs": {"network_manager_device_ref": "inst.net.mgr"}}
    ctx = _context(manifest)
    _publish_rows(
        ctx,
        [{"group": "services", "instance": "inst.net.mgr", "class_ref": "class.service.web_ui", "layer": "L5"}],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7812" for diag in result.diagnostics)

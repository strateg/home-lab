#!/usr/bin/env python3
"""Integration tests for security policy refs validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.security_policy_refs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
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


def _base_rows() -> list[dict]:
    return [
        {
            "group": "security_policies",
            "instance": "sec-policy-default",
            "class_ref": "class.security.policy",
            "layer": "L7",
        },
        {
            "group": "services",
            "instance": "svc-a",
            "class_ref": "class.service.web_ui",
            "layer": "L5",
            "extensions": {"security_policy_ref": "sec-policy-default"},
        },
        {
            "group": "operations",
            "instance": "backup-a",
            "class_ref": "class.operations.backup",
            "layer": "L7",
            "extensions": {"security_policy_ref": "sec-policy-default"},
        },
    ]


def test_security_policy_refs_validator_accepts_valid_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_security_policy_refs_validator_rejects_unknown_policy_ref():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["security_policy_ref"] = "sec-policy-missing"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7859" for diag in result.diagnostics)


def test_security_policy_refs_validator_rejects_non_string_policy_ref():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[1]["extensions"]["security_policy_ref"] = {"id": "sec-policy-default"}  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7859" for diag in result.diagnostics)


def test_security_policy_refs_validator_accepts_legacy_group_based_policy_row():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[0]["group"] = "security_policy"  # type: ignore[index]
    rows[0]["class_ref"] = "class.misc"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_security_policy_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7859" for diag in result.diagnostics)

#!/usr/bin/env python3
"""Integration tests for DNS refs validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.dns_refs"


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
        {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
        {"group": "lxc", "instance": "lxc-a", "class_ref": "class.compute.workload.container", "layer": "L4"},
        {"group": "services", "instance": "svc-a", "class_ref": "class.service.web_ui", "layer": "L5"},
        {
            "group": "services",
            "instance": "svc-dns",
            "class_ref": "class.service.dns",
            "layer": "L5",
            "extensions": {
                "zones": [
                    {
                        "id": "zone.local",
                        "records": [
                            {"name": "router", "device_ref": "srv-a"},
                            {"name": "container", "lxc_ref": "lxc-a"},
                            {"name": "app", "service_ref": "svc-a"},
                        ],
                    }
                ]
            },
        },
    ]


def test_dns_refs_validator_accepts_valid_dns_refs():
    registry = _registry()
    ctx = _context()
    _publish_rows(ctx, _base_rows())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_dns_refs_validator_rejects_unknown_service_ref():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["extensions"]["zones"][0]["records"][2]["service_ref"] = "svc-missing"  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7856" for diag in result.diagnostics)


def test_dns_refs_validator_accepts_direct_records_payload_shape():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["extensions"] = {  # type: ignore[index]
        "records": [
            {"name": "router", "device_ref": "srv-a"},
            {"name": "container", "lxc_ref": "lxc-a"},
            {"name": "app", "service_ref": "svc-a"},
        ]
    }
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_dns_refs_validator_rejects_non_object_record_entry():
    registry = _registry()
    ctx = _context()
    rows = _base_rows()
    rows[-1]["extensions"] = {"records": ["legacy-record"]}  # type: ignore[index]
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7856" for diag in result.diagnostics)


def test_dns_refs_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7856" for diag in result.diagnostics)

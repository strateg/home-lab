#!/usr/bin/env python3
"""Integration tests for DeclarativeReferenceValidator (Wave 2 baseline)."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginStatus
from kernel.plugin_base import Stage
from plugins.validators.declarative_reference_validator import DeclarativeReferenceValidator


def _context(*, config: dict | None = None, objects: dict | None = None) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects=objects or {},
        instance_bindings={"instance_bindings": {}},
        config=config or {},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()


def test_declarative_reference_validator_accepts_valid_dns_backup_service_dependencies():
    plugin = DeclarativeReferenceValidator("validator.declarative_refs", "1.x")
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
        {"group": "lxc", "instance": "lxc-a", "class_ref": "class.compute.workload.container", "layer": "L4"},
        {"group": "services", "instance": "svc-a", "class_ref": "class.service.web_ui", "layer": "L5"},
        {"group": "storage", "instance": "pool-a", "class_ref": "class.storage.pool", "layer": "L3"},
        {"group": "storage", "instance": "asset-a", "class_ref": "class.storage.data_asset", "layer": "L3"},
        {
            "group": "services",
            "instance": "svc-dns",
            "class_ref": "class.service.dns",
            "layer": "L5",
            "extensions": {
                "records": [
                    {"name": "router", "device_ref": "srv-a"},
                    {"name": "container", "lxc_ref": "lxc-a"},
                    {"name": "app", "service_ref": "svc-a"},
                ]
            },
        },
        {
            "group": "operations",
            "instance": "backup-a",
            "class_ref": "class.operations.backup",
            "layer": "L6",
            "extensions": {
                "destination_ref": "pool-a",
                "targets": [{"data_asset_ref": "asset-a"}],
            },
        },
        {
            "group": "services",
            "instance": "svc-b",
            "class_ref": "class.service.worker",
            "layer": "L5",
            "extensions": {
                "data_asset_refs": ["asset-a"],
                "dependencies": [{"service_ref": "svc-a"}],
            },
        },
    ]
    _publish_rows(ctx, rows)

    ctx._set_execution_context("validator.declarative_refs", {"base.compiler.instance_rows"}, stage=Stage.VALIDATE)
    try:
        result = plugin.execute(ctx, Stage.VALIDATE)
    finally:
        ctx._clear_execution_context()

    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_declarative_reference_validator_emits_dns_error_for_unknown_service_ref():
    plugin = DeclarativeReferenceValidator("validator.declarative_refs", "1.x")
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
        {
            "group": "services",
            "instance": "svc-dns",
            "class_ref": "class.service.dns",
            "layer": "L5",
            "extensions": {"records": [{"service_ref": "svc-missing"}]},
        },
    ]
    _publish_rows(ctx, rows)

    ctx._set_execution_context("validator.declarative_refs", {"base.compiler.instance_rows"}, stage=Stage.VALIDATE)
    try:
        result = plugin.execute(ctx, Stage.VALIDATE)
    finally:
        ctx._clear_execution_context()

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7856" for diag in result.diagnostics)


def test_declarative_reference_validator_accepts_valid_network_core_and_power_source_refs():
    plugin = DeclarativeReferenceValidator("validator.declarative_refs", "1.x")
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "rtr-a", "class_ref": "class.router", "layer": "L1"},
        {"group": "devices", "instance": "srv-a", "class_ref": "class.compute.hypervisor", "layer": "L1"},
        {"group": "network", "instance": "inst.zone.a", "class_ref": "class.network.trust_zone", "layer": "L2"},
        {
            "group": "network",
            "instance": "inst.bridge.a",
            "class_ref": "class.network.bridge",
            "layer": "L2",
            "extensions": {"host_ref": "srv-a"},
        },
        {
            "group": "network",
            "instance": "inst.vlan.a",
            "class_ref": "class.network.vlan",
            "layer": "L2",
            "extensions": {
                "bridge_ref": "inst.bridge.a",
                "trust_zone_ref": "inst.zone.a",
                "managed_by_ref": "rtr-a",
            },
        },
        {"group": "devices", "instance": "ups-main", "class_ref": "class.power.ups", "layer": "L1", "extensions": {}},
        {
            "group": "devices",
            "instance": "pdu-rack",
            "class_ref": "class.power.pdu",
            "layer": "L1",
            "extensions": {"power": {"source_ref": "ups-main"}},
        },
        {
            "group": "devices",
            "instance": "rtr-b",
            "class_ref": "class.router",
            "layer": "L1",
            "extensions": {"power": {"source_ref": "pdu-rack", "outlet_ref": "A1"}},
        },
    ]
    _publish_rows(ctx, rows)

    ctx._set_execution_context("validator.declarative_refs", {"base.compiler.instance_rows"}, stage=Stage.VALIDATE)
    try:
        result = plugin.execute(ctx, Stage.VALIDATE)
    finally:
        ctx._clear_execution_context()

    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_declarative_reference_validator_emits_network_core_error_for_unknown_bridge_ref():
    plugin = DeclarativeReferenceValidator("validator.declarative_refs", "1.x")
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "rtr-a", "class_ref": "class.router", "layer": "L1"},
        {"group": "network", "instance": "inst.zone.a", "class_ref": "class.network.trust_zone", "layer": "L2"},
        {
            "group": "network",
            "instance": "inst.vlan.a",
            "class_ref": "class.network.vlan",
            "layer": "L2",
            "extensions": {
                "bridge_ref": "inst.bridge.missing",
                "trust_zone_ref": "inst.zone.a",
                "managed_by_ref": "rtr-a",
            },
        },
    ]
    _publish_rows(ctx, rows)

    ctx._set_execution_context("validator.declarative_refs", {"base.compiler.instance_rows"}, stage=Stage.VALIDATE)
    try:
        result = plugin.execute(ctx, Stage.VALIDATE)
    finally:
        ctx._clear_execution_context()

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7833" for diag in result.diagnostics)


def test_declarative_reference_validator_emits_power_source_error_for_duplicate_outlet():
    plugin = DeclarativeReferenceValidator("validator.declarative_refs", "1.x")
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "pdu-rack", "class_ref": "class.power.pdu", "layer": "L1", "extensions": {}},
        {
            "group": "devices",
            "instance": "rtr-a",
            "class_ref": "class.router",
            "layer": "L1",
            "extensions": {"power": {"source_ref": "pdu-rack", "outlet_ref": "A1"}},
        },
        {
            "group": "devices",
            "instance": "rtr-b",
            "class_ref": "class.router",
            "layer": "L1",
            "extensions": {"power": {"source_ref": "pdu-rack", "outlet_ref": "A1"}},
        },
    ]
    _publish_rows(ctx, rows)

    ctx._set_execution_context("validator.declarative_refs", {"base.compiler.instance_rows"}, stage=Stage.VALIDATE)
    try:
        result = plugin.execute(ctx, Stage.VALIDATE)
    finally:
        ctx._clear_execution_context()

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7805" for diag in result.diagnostics)

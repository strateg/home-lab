#!/usr/bin/env python3
# ADR: 0062, 0088
"""Integration tests for DeclarativeReferenceValidator (Wave 2 baseline)."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginStatus
from kernel.plugin_base import Stage
from plugins.validators.declarative_reference_validator import DeclarativeReferenceValidator

from tests.helpers.plugin_execution import publish_for_test, run_plugin_for_test


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
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)


def _execute(plugin: DeclarativeReferenceValidator, ctx: PluginContext):
    return run_plugin_for_test(
        plugin,
        ctx,
        Stage.VALIDATE,
        consumes_keys={"base.compiler.instance_rows", "base.compiler.effective_model"},
    )


def _publish_enforcer_resolution(ctx: PluginContext, resolution: dict) -> None:
    publish_for_test(ctx, "base.compiler.effective_model", "enforcer_resolution", resolution)


def test_declarative_reference_validator_accepts_valid_dns_backup_service_dependencies():
    plugin = DeclarativeReferenceValidator("validator.declarative_refs", "1.x")
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
        {"group": "lxc", "instance": "lxc-a", "class_ref": "class.compute.workload.lxc", "layer": "L4"},
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

    result = _execute(plugin, ctx)

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

    result = _execute(plugin, ctx)

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
    _publish_enforcer_resolution(
        ctx,
        {"rtr-a": {"type": "network", "adapter": None, "adapter_version": None, "considered": [], "compatible": [], "reason": "test"}},
    )

    result = _execute(plugin, ctx)

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
    _publish_enforcer_resolution(
        ctx,
        {"rtr-a": {"type": "network", "adapter": None, "adapter_version": None, "considered": [], "compatible": [], "reason": "test"}},
    )

    result = _execute(plugin, ctx)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7833" for diag in result.diagnostics)


def test_declarative_reference_validator_emits_e7019_when_vlan_manager_has_no_network_enforcer_type():
    plugin = DeclarativeReferenceValidator("validator.declarative_refs", "1.x")
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "rtr-a", "class_ref": "class.router", "layer": "L1"},
        {"group": "network", "instance": "inst.zone.a", "class_ref": "class.network.trust_zone", "layer": "L2"},
        {
            "group": "network",
            "instance": "inst.bridge.a",
            "class_ref": "class.network.bridge",
            "layer": "L2",
            "extensions": {},
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
    ]
    _publish_rows(ctx, rows)
    # No enforcer_resolution entry for 'rtr-a' at all: D-TYPE-1 found no
    # device-kind capability, so the instance is omitted (same shape as
    # ENFORCER-AXIS-CONFORMANCE.md section 4's "no enforcement capability"
    # counterexample).
    _publish_enforcer_resolution(ctx, {})

    result = _execute(plugin, ctx)

    assert result.status == PluginStatus.FAILED
    e7019 = [diag for diag in result.diagnostics if diag.code == "E7019"]
    assert len(e7019) == 1
    assert e7019[0].path == "instance:network:inst.vlan.a.managed_by_ref"


def test_declarative_reference_validator_emits_e7019_when_vlan_manager_resolves_to_compute_enforcer():
    plugin = DeclarativeReferenceValidator("validator.declarative_refs", "1.x")
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
        {"group": "network", "instance": "inst.zone.a", "class_ref": "class.network.trust_zone", "layer": "L2"},
        {
            "group": "network",
            "instance": "inst.bridge.a",
            "class_ref": "class.network.bridge",
            "layer": "L2",
            "extensions": {},
        },
        {
            "group": "network",
            "instance": "inst.vlan.a",
            "class_ref": "class.network.vlan",
            "layer": "L2",
            "extensions": {
                "bridge_ref": "inst.bridge.a",
                "trust_zone_ref": "inst.zone.a",
                "managed_by_ref": "srv-a",
            },
        },
    ]
    _publish_rows(ctx, rows)
    # 'srv-a' resolves as a compute-type enforcer (ADR-0110 hypervisor case):
    # valid for a security_matrix's managed_by_ref, not for a VLAN's.
    _publish_enforcer_resolution(
        ctx,
        {"srv-a": {"type": "compute", "adapter": None, "adapter_version": None, "considered": [], "compatible": [], "reason": "test"}},
    )

    result = _execute(plugin, ctx)

    assert result.status == PluginStatus.FAILED
    e7019 = [diag for diag in result.diagnostics if diag.code == "E7019"]
    assert len(e7019) == 1
    assert e7019[0].path == "instance:network:inst.vlan.a.managed_by_ref"


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

    result = _execute(plugin, ctx)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7805" for diag in result.diagnostics)


def test_declarative_reference_validator_emits_e7019_when_routing_policy_manager_resolves_to_compute_enforcer():
    plugin = DeclarativeReferenceValidator("validator.declarative_refs", "1.x")
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.router", "layer": "L1"},
        {
            "group": "network",
            "instance": "inst.routing_policy.a",
            "class_ref": "class.network.routing_policy",
            "layer": "L2",
            "extensions": {"managed_by_ref": "srv-a"},
        },
    ]
    _publish_rows(ctx, rows)
    # Routing-policy's managed_by_ref shares VLAN's strict "network" check
    # (E7019), not security_matrix/firewall_policy's permissive one: a
    # router's routing table is not something a hypervisor can take over.
    _publish_enforcer_resolution(
        ctx,
        {"srv-a": {"type": "compute", "adapter": None, "adapter_version": None, "considered": [], "compatible": [], "reason": "test"}},
    )

    result = _execute(plugin, ctx)

    assert result.status == PluginStatus.FAILED
    e7019 = [diag for diag in result.diagnostics if diag.code == "E7019"]
    assert len(e7019) == 1
    assert e7019[0].path == "instance:network:inst.routing_policy.a.managed_by_ref"


def test_declarative_reference_validator_accepts_routing_policy_with_network_enforcer():
    plugin = DeclarativeReferenceValidator("validator.declarative_refs", "1.x")
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "rtr-a", "class_ref": "class.router", "layer": "L1"},
        {
            "group": "network",
            "instance": "inst.routing_policy.a",
            "class_ref": "class.network.routing_policy",
            "layer": "L2",
            "extensions": {"managed_by_ref": "rtr-a"},
        },
    ]
    _publish_rows(ctx, rows)
    _publish_enforcer_resolution(
        ctx,
        {"rtr-a": {"type": "network", "adapter": None, "adapter_version": None, "considered": [], "compatible": [], "reason": "test"}},
    )

    result = _execute(plugin, ctx)

    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_declarative_reference_validator_emits_e7026_when_firewall_policy_manager_has_no_resolved_type():
    plugin = DeclarativeReferenceValidator("validator.declarative_refs", "1.x")
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "rtr-a", "class_ref": "class.router", "layer": "L1"},
        {
            "group": "firewall",
            "instance": "inst.fw.a",
            "class_ref": "class.network.firewall_policy",
            "layer": "L2",
            "extensions": {"managed_by_ref": "rtr-a"},
        },
    ]
    _publish_rows(ctx, rows)
    # No enforcer_resolution entry for 'rtr-a': D-TYPE-1 found no device-kind
    # capability, so the instance is omitted.
    _publish_enforcer_resolution(ctx, {})

    result = _execute(plugin, ctx)

    assert result.status == PluginStatus.FAILED
    e7026 = [diag for diag in result.diagnostics if diag.code == "E7026"]
    assert len(e7026) == 1
    assert e7026[0].path == "instance:firewall:inst.fw.a.managed_by_ref"


def test_declarative_reference_validator_accepts_firewall_policy_with_compute_enforcer():
    plugin = DeclarativeReferenceValidator("validator.declarative_refs", "1.x")
    ctx = _context()
    rows = [
        {"group": "devices", "instance": "srv-a", "class_ref": "class.compute.hypervisor", "layer": "L1"},
        {
            "group": "firewall",
            "instance": "inst.fw.a",
            "class_ref": "class.network.firewall_policy",
            "layer": "L2",
            "extensions": {"managed_by_ref": "srv-a"},
        },
    ]
    _publish_rows(ctx, rows)
    # Firewall-policy's managed_by_ref shares security_matrix's permissive
    # check (E7026 vs E7018): a hypervisor is a valid enforcer (ADR-0110),
    # unlike VLAN/routing_policy's strict "network" requirement.
    _publish_enforcer_resolution(
        ctx,
        {"srv-a": {"type": "compute", "adapter": None, "adapter_version": None, "considered": [], "compatible": [], "reason": "test"}},
    )

    result = _execute(plugin, ctx)

    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []

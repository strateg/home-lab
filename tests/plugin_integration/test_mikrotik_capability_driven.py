#!/usr/bin/env python3
# ADR: 0106
"""Tests for capability-driven MikroTik Terraform generation."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

from tests.helpers.plugin_execution import publish_for_test, run_plugin_for_test

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage  # noqa: E402
from plugins.generators.object_projection_loader import load_object_projection_module  # noqa: E402

_MIKROTIK_PROJECTIONS = load_object_projection_module("mikrotik")
_raw_build_mikrotik_projection = _MIKROTIK_PROJECTIONS.build_mikrotik_projection


def _load_capability_flags_module():
    # W07 migration order item 1: capability-flag derivation moved from the
    # projection (generate stage) to a compile-stage compiler plugin. Unit
    # tests of the derivation logic itself now load it from there.
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "compilers"
        / "capability_flags_compiler.py"
    )
    spec = importlib.util.spec_from_file_location("test_mikrotik_capability_flags_compiler", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CAPABILITY_FLAGS_MODULE = _load_capability_flags_module()
_derive_mikrotik_capability_flags = _CAPABILITY_FLAGS_MODULE._derive_capability_flags
_extract_capabilities = _CAPABILITY_FLAGS_MODULE._extract_capabilities
_resolved_object_ref = _CAPABILITY_FLAGS_MODULE._resolved_object_ref


def _load_wireguard_tunnels_module():
    # W07 migration order item 4a: WireGuard tunnel derivation moved from the
    # projection (generate stage) to a compile-stage compiler plugin.
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "compilers"
        / "wireguard_tunnels_compiler.py"
    )
    spec = importlib.util.spec_from_file_location("test_mikrotik_wireguard_tunnels_compiler", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_WIREGUARD_TUNNELS_MODULE = _load_wireguard_tunnels_module()
_extract_wireguard_tunnels = _WIREGUARD_TUNNELS_MODULE._extract_wireguard_tunnels


def _load_containers_module():
    # W07 migration order item 4b: container derivation moved from the
    # projection (generate stage) to a compile-stage compiler plugin.
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "compilers"
        / "containers_compiler.py"
    )
    spec = importlib.util.spec_from_file_location("test_mikrotik_containers_compiler", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CONTAINERS_MODULE = _load_containers_module()
_extract_containers = _CONTAINERS_MODULE._extract_containers


def _load_wifi_config_module():
    # W07 migration order item 4c: WiFi config derivation moved from the
    # projection (generate stage) to a compile-stage compiler plugin.
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "compilers"
        / "wifi_config_compiler.py"
    )
    spec = importlib.util.spec_from_file_location("test_mikrotik_wifi_config_compiler", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_WIFI_CONFIG_MODULE = _load_wifi_config_module()
_extract_wifi_config = _WIFI_CONFIG_MODULE._extract_wifi_config


def _load_routing_policies_module():
    # W07 migration order item 4d: routing-policy derivation moved from the
    # projection (generate stage) to a compile-stage compiler plugin.
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "compilers"
        / "routing_policies_compiler.py"
    )
    spec = importlib.util.spec_from_file_location("test_mikrotik_routing_policies_compiler", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ROUTING_POLICIES_MODULE = _load_routing_policies_module()
_build_routing_policy_entry = _ROUTING_POLICIES_MODULE._build_routing_policy_entry


def _load_mac_vlan_assignments_module():
    # W07 migration order item 4e: MAC-to-VLAN assignment derivation moved
    # from the projection (generate stage) to a compile-stage compiler plugin.
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "compilers"
        / "mac_vlan_assignments_compiler.py"
    )
    spec = importlib.util.spec_from_file_location("test_mikrotik_mac_vlan_assignments_compiler", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MAC_VLAN_ASSIGNMENTS_MODULE = _load_mac_vlan_assignments_module()
_extract_mac_vlan_assignments = _MAC_VLAN_ASSIGNMENTS_MODULE._extract_mac_vlan_assignments
_build_vlan_id_index = _MAC_VLAN_ASSIGNMENTS_MODULE._build_vlan_id_index


def _load_bridge_vlans_module():
    # W07 migration order item 4f: bridge-VLAN derivation moved from the
    # projection (generate stage) to a compile-stage compiler plugin.
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "compilers"
        / "bridge_vlans_compiler.py"
    )
    spec = importlib.util.spec_from_file_location("test_mikrotik_bridge_vlans_compiler", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BRIDGE_VLANS_MODULE = _load_bridge_vlans_module()
_extract_bridge_vlans = _BRIDGE_VLANS_MODULE._extract_bridge_vlans


def _load_vlan_entries_module():
    # W07 migration order item 4g: VLAN-entry derivation moved from the
    # projection (generate stage) to a compile-stage compiler plugin.
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "compilers"
        / "vlan_entries_compiler.py"
    )
    spec = importlib.util.spec_from_file_location("test_mikrotik_vlan_entries_compiler", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_VLAN_ENTRIES_MODULE = _load_vlan_entries_module()
_build_vlan_entry = _VLAN_ENTRIES_MODULE._build_vlan_entry

# The producer the manifest lets this generator subscribe to. Both of its keys -
# `security_matrices` and `vlan_cidr_map` - are declared `required: true`, because
# the projection derives no substitute for either.
_SECURITY_MATRIX_COMPILER = "base.compiler.security_matrix"
_CAPABILITY_FLAGS_COMPILER = "object.mikrotik.compiler.capability_flags"
_WIREGUARD_TUNNELS_COMPILER = "object.mikrotik.compiler.wireguard_tunnels"
_CONTAINERS_COMPILER = "object.mikrotik.compiler.containers"
_WIFI_CONFIG_COMPILER = "object.mikrotik.compiler.wifi_config"
_ROUTING_POLICIES_COMPILER = "object.mikrotik.compiler.routing_policies"
_MAC_VLAN_ASSIGNMENTS_COMPILER = "object.mikrotik.compiler.mac_vlan_assignments"
_BRIDGE_VLANS_COMPILER = "object.mikrotik.compiler.bridge_vlans"
_VLAN_ENTRIES_COMPILER = "object.mikrotik.compiler.vlan_entries"
_CONSUMED_KEYS = (
    _SECURITY_MATRIX_COMPILER,
    _CAPABILITY_FLAGS_COMPILER,
    _WIREGUARD_TUNNELS_COMPILER,
    _CONTAINERS_COMPILER,
    _WIFI_CONFIG_COMPILER,
    _ROUTING_POLICIES_COMPILER,
    _MAC_VLAN_ASSIGNMENTS_COMPILER,
    _BRIDGE_VLANS_COMPILER,
    _VLAN_ENTRIES_COMPILER,
)


def _mikrotik_routers_and_network(compiled_json: dict) -> tuple[set[str], list[dict], list[dict], list[dict]]:
    semantic = _semanticize(compiled_json)
    instances = semantic.get("instances")
    devices = instances.get("devices", []) if isinstance(instances, dict) else []
    network_rows = instances.get("network", []) if isinstance(instances, dict) else []
    container_rows = instances.get("routeros_container", []) if isinstance(instances, dict) else []
    routers = [
        row for row in devices if isinstance(row, dict) and _resolved_object_ref(row).startswith("obj.mikrotik.")
    ]
    router_ids = {row.get("instance_id") for row in routers}
    return (
        {r for r in router_ids if isinstance(r, str) and r},
        routers,
        [r for r in network_rows if isinstance(r, dict)],
        [r for r in container_rows if isinstance(r, dict)],
    )


def _derive_flags_for_fixture(compiled_json: dict) -> dict:
    """Same derivation the real compile-stage compiler performs, applied to a
    test fixture's compiled_json directly (W07 migration order item 1)."""
    semantic = _semanticize(compiled_json)
    instances = semantic.get("instances")
    devices = instances.get("devices", []) if isinstance(instances, dict) else []
    routers = [
        row for row in devices if isinstance(row, dict) and _resolved_object_ref(row).startswith("obj.mikrotik.")
    ]
    return _derive_mikrotik_capability_flags(routers)


def _derive_wireguard_tunnels_for_fixture(compiled_json: dict) -> dict:
    """Same derivation the real compile-stage compiler performs, applied to a
    test fixture's compiled_json directly (W07 migration order item 4a)."""
    router_ids, _, network_rows, _ = _mikrotik_routers_and_network(compiled_json)
    return _extract_wireguard_tunnels(network_rows, router_ids, {})


def _derive_containers_for_fixture(compiled_json: dict) -> list[dict]:
    """Same derivation the real compile-stage compiler performs, applied to a
    test fixture's compiled_json directly (W07 migration order item 4b)."""
    router_ids, _, _, container_rows = _mikrotik_routers_and_network(compiled_json)
    return _extract_containers(container_rows, router_ids)


def _derive_wifi_config_for_fixture(compiled_json: dict) -> dict:
    """Same derivation the real compile-stage compiler performs, applied to a
    test fixture's compiled_json directly (W07 migration order item 4c)."""
    _, routers, _, _ = _mikrotik_routers_and_network(compiled_json)
    return _extract_wifi_config(routers)


def _derive_routing_policies_for_fixture(compiled_json: dict) -> list[dict]:
    """Same derivation the real compile-stage compiler performs, applied to a
    test fixture's compiled_json directly (W07 migration order item 4d).

    Replicates the plugin's own row-selection/managed_by_ref-resolution
    loop, not just a single all-routers call.
    """
    router_ids, _, network_rows, _ = _mikrotik_routers_and_network(compiled_json)
    default_router_id = next(iter(sorted(router_ids)), "")
    routing_policies: list[dict] = []
    for row in network_rows:
        object_ref = _resolved_object_ref(row)
        if "routing_policy" not in object_ref:
            continue
        inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
        managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
        if not managed_by_ref and len(router_ids) == 1:
            managed_by_ref = default_router_id
        if managed_by_ref in router_ids:
            routing_policies.append(
                _build_routing_policy_entry(row, managed_by_ref=managed_by_ref, vlan_cidr_index={})
            )
    return routing_policies


def _derive_mac_vlan_assignments_for_fixture(compiled_json: dict) -> list[dict]:
    """Same derivation the real compile-stage compiler performs, applied to a
    test fixture's compiled_json directly (W07 migration order item 4e).

    Replicates the plugin's own vlan_id_index-building slice of the shared
    network-row loop, the same discipline item 4d's helper above established.
    """
    semantic = _semanticize(compiled_json)
    router_ids, _, network_rows, _ = _mikrotik_routers_and_network(compiled_json)
    instances = semantic.get("instances")
    devices = instances.get("devices", []) if isinstance(instances, dict) else []
    objects_map = semantic.get("objects", {})
    if not isinstance(objects_map, dict):
        objects_map = {}
    default_router_id = next(iter(sorted(router_ids)), "")
    vlan_id_index = _build_vlan_id_index(
        network_rows,
        router_ids=router_ids,
        default_router_id=default_router_id,
        objects_map=objects_map,
    )
    return _extract_mac_vlan_assignments(
        {"network": network_rows, "devices": [row for row in devices if isinstance(row, dict)]},
        vlan_id_index,
    )


def _derive_bridge_vlans_for_fixture(compiled_json: dict) -> list[dict]:
    """Same derivation the real compile-stage compiler performs, applied to a
    test fixture's compiled_json directly (W07 migration order item 4f).

    Depends on `wifi_config` (item 4c)'s already-derived datapath/interface
    shape, the same forward dependency the W07 decision document recorded
    when 4c moved.
    """
    _, routers, _, _ = _mikrotik_routers_and_network(compiled_json)
    wifi_data = _derive_wifi_config_for_fixture(compiled_json)
    return _extract_bridge_vlans(routers, wifi_data)


def _derive_vlans_for_fixture(compiled_json: dict) -> list[dict]:
    """Same derivation the real compile-stage compiler performs, applied to a
    test fixture's compiled_json directly (W07 migration order item 4g).

    Replicates the plugin's own row-selection/managed_by_ref-resolution
    loop (VLAN branch of the shared network-row loop), the same discipline
    item 4d's helper above established.
    """
    semantic = _semanticize(compiled_json)
    instances = semantic.get("instances")
    network_rows = instances.get("network", []) if isinstance(instances, dict) else []
    devices = instances.get("devices", []) if isinstance(instances, dict) else []
    routers = [
        row for row in devices if isinstance(row, dict) and _resolved_object_ref(row).startswith("obj.mikrotik.")
    ]
    router_ids = {row.get("instance_id") for row in routers if isinstance(row.get("instance_id"), str)}
    default_router_id = next(iter(sorted(router_ids)), "")
    objects_map = semantic.get("objects", {})
    if not isinstance(objects_map, dict):
        objects_map = {}
    vlans: list[dict] = []
    for row in network_rows:
        if not isinstance(row, dict):
            continue
        object_ref = _resolved_object_ref(row)
        if "vlan" not in object_ref or "routing_policy" in object_ref:
            continue
        inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
        managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
        if not managed_by_ref and len(router_ids) == 1:
            managed_by_ref = default_router_id
        if not managed_by_ref:
            allocations = inst_data.get("ip_allocations")
            if isinstance(allocations, list):
                for item in allocations:
                    if not isinstance(item, dict):
                        continue
                    device_ref = str(item.get("device_ref") or "").strip()
                    if device_ref in router_ids:
                        managed_by_ref = device_ref
                        break
        if managed_by_ref in router_ids:
            vlans.append(_build_vlan_entry(row, managed_by_ref=managed_by_ref, objects_map=objects_map))
    return vlans


def _semanticize(compiled_json: dict) -> dict:
    payload = copy.deepcopy(compiled_json)
    instances = payload.get("instances")
    if not isinstance(instances, dict):
        return payload
    for rows in instances.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            object_ref = row.pop("object_ref", None)
            class_ref = row.pop("class_ref", None)
            if not isinstance(object_ref, str) and not isinstance(class_ref, str):
                continue
            instance_block = row.get("instance")
            if not isinstance(instance_block, dict):
                instance_block = {}
                row["instance"] = instance_block
            if isinstance(object_ref, str) and object_ref:
                instance_block.setdefault("materializes_object", object_ref)
            if isinstance(class_ref, str) and class_ref:
                instance_block.setdefault("materializes_class", class_ref)
    return payload


def build_mikrotik_projection(compiled_json: dict, **kwargs) -> dict:
    """Channels stated empty: these fixtures declare no matrices and no domains.

    They are required arguments now - the projection derives no substitute for
    `base.compiler.security_matrix` - so omission is an error and `{}` is a claim.

    `capability_flags` (W07 migration order item 1), `wireguard_tunnels`
    (W07 migration order item 4a), `containers` (W07 migration order item
    4b), `wifi_config` (W07 migration order item 4c), `routing_policies`
    (W07 migration order item 4d), `mac_vlan_assignments` (W07 migration
    order item 4e), `bridge_vlans` (W07 migration order item 4f) and
    `vlans` (W07 migration order item 4g) are likewise required and are
    auto-derived here from the same devices/network/container rows the real
    compile-stage compiler plugins read, unless a test passes its own value
    to exercise a specific case.
    """
    semantic = _semanticize(compiled_json)
    kwargs.setdefault("composed_matrices_by_enforcer", {})
    kwargs.setdefault("vlan_cidr_map", {})
    if "capability_flags" not in kwargs:
        instances = semantic.get("instances")
        devices = instances.get("devices", []) if isinstance(instances, dict) else []
        routers = [
            row for row in devices if isinstance(row, dict) and _resolved_object_ref(row).startswith("obj.mikrotik.")
        ]
        kwargs["capability_flags"] = _derive_mikrotik_capability_flags(routers)
    if (
        "wireguard_tunnels" not in kwargs
        or "containers" not in kwargs
        or "wifi_config" not in kwargs
    ):
        router_ids, routers, network_rows, container_rows = _mikrotik_routers_and_network(compiled_json)
        kwargs.setdefault("wireguard_tunnels", _extract_wireguard_tunnels(network_rows, router_ids, {}))
        kwargs.setdefault("containers", _extract_containers(container_rows, router_ids))
        kwargs.setdefault("wifi_config", _extract_wifi_config(routers))
    if "routing_policies" not in kwargs:
        kwargs["routing_policies"] = _derive_routing_policies_for_fixture(compiled_json)
    if "mac_vlan_assignments" not in kwargs:
        kwargs["mac_vlan_assignments"] = _derive_mac_vlan_assignments_for_fixture(compiled_json)
    if "bridge_vlans" not in kwargs:
        kwargs["bridge_vlans"] = _derive_bridge_vlans_for_fixture(compiled_json)
    if "vlans" not in kwargs:
        kwargs["vlans"] = _derive_vlans_for_fixture(compiled_json)
    return _raw_build_mikrotik_projection(semantic, **kwargs)


def _load_generator_class():
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "generators"
        / "terraform_mikrotik_generator.py"
    )
    spec = importlib.util.spec_from_file_location("test_object_mikrotik_terraform_generator", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TerraformMikroTikGenerator


TerraformMikroTikGenerator = _load_generator_class()


class TestCapabilityExtraction:
    """Tests for capability extraction helpers."""

    def test_extract_capabilities_from_list(self) -> None:
        row = {
            "instance_id": "rtr-test",
            "capabilities": [
                "cap.net.overlay.vpn.wireguard.server",
                "cap.net.platform.containers",
            ],
        }
        caps = _extract_capabilities(row)
        assert "cap.net.overlay.vpn.wireguard.server" in caps
        assert "cap.net.platform.containers" in caps

    def test_extract_capabilities_from_derived(self) -> None:
        row = {
            "instance_id": "rtr-test",
            "derived_capabilities": ["cap.os.routeros", "cap.arch.arm64"],
        }
        caps = _extract_capabilities(row)
        assert "cap.os.routeros" in caps
        assert "cap.arch.arm64" in caps

    def test_extract_capabilities_empty(self) -> None:
        row = {"instance_id": "rtr-test"}
        caps = _extract_capabilities(row)
        assert caps == set()

    def test_extract_capabilities_mixed(self) -> None:
        row = {
            "instance_id": "rtr-test",
            "capabilities": ["cap.net.overlay.vpn.wireguard.server"],
            "derived_capabilities": ["cap.os.routeros"],
        }
        caps = _extract_capabilities(row)
        assert len(caps) == 2


class TestMikroTikCapabilityFlags:
    """Tests for capability flag derivation."""

    def test_wireguard_capability_flag(self) -> None:
        routers = [
            {
                "instance_id": "rtr-test",
                "object_ref": "obj.mikrotik.test",
                "capabilities": ["cap.net.overlay.vpn.wireguard.server"],
            }
        ]
        flags = _derive_mikrotik_capability_flags(routers)
        assert flags["has_wireguard"] is True
        assert flags["has_containers"] is False

    def test_containers_capability_flag(self) -> None:
        routers = [
            {
                "instance_id": "rtr-test",
                "object_ref": "obj.mikrotik.test",
                "capabilities": ["cap.net.platform.containers"],
            }
        ]
        flags = _derive_mikrotik_capability_flags(routers)
        assert flags["has_containers"] is True
        assert flags["has_wireguard"] is False

    def test_chateau_implicit_capabilities(self) -> None:
        """Chateau models have LTE and containers capabilities from object definition."""
        # ADR0078: Capabilities come from object definitions, resolved during compilation
        routers = [
            {
                "instance_id": "rtr-mikrotik-chateau",
                "object_ref": "obj.mikrotik.chateau_lte7_ax",
                # These capabilities are defined in obj.mikrotik.chateau_lte7_ax.yaml
                # and would be resolved during compilation
                "enabled_capabilities": [
                    "cap.net.platform.containers",
                    "cap.net.interface.lte",
                ],
            }
        ]
        flags = _derive_mikrotik_capability_flags(routers)
        assert flags["has_containers"] is True
        assert flags["has_lte"] is True

    def test_qos_capability_flags(self) -> None:
        routers = [
            {
                "instance_id": "rtr-test",
                "object_ref": "obj.mikrotik.test",
                "capabilities": ["cap.net.l3.qos.advanced"],
            }
        ]
        flags = _derive_mikrotik_capability_flags(routers)
        assert flags["has_qos_advanced"] is True
        assert flags["has_qos_basic"] is False

    def test_no_capabilities(self) -> None:
        routers = [
            {
                "instance_id": "rtr-test",
                "object_ref": "obj.mikrotik.test",
            }
        ]
        flags = _derive_mikrotik_capability_flags(routers)
        assert flags["has_wireguard"] is False
        assert flags["has_containers"] is False
        assert flags["has_qos_basic"] is False


class TestMikroTikProjectionCapabilities:
    """Tests for capability flags in MikroTik projection."""

    def test_projection_includes_capabilities(self) -> None:
        compiled_json = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-test",
                        "object_ref": "obj.mikrotik.test",
                        "capabilities": ["cap.net.overlay.vpn.wireguard.server"],
                    }
                ],
                "network": [],
                "services": [],
            }
        }
        projection = build_mikrotik_projection(compiled_json)
        assert "capabilities" in projection
        assert projection["capabilities"]["has_wireguard"] is True

    def test_projection_does_not_use_legacy_group_names(self) -> None:
        compiled_json = {
            "instances": {
                "l1_devices": [
                    {
                        "instance_id": "rtr-test",
                        "object_ref": "obj.mikrotik.test",
                        "capabilities": ["cap.net.overlay.vpn.wireguard.server"],
                    }
                ],
                "l2_network": [],
                "l5_services": [],
            }
        }
        projection = build_mikrotik_projection(compiled_json)
        assert projection["counts"]["routers"] == 0
        assert projection["capabilities"]["has_wireguard"] is False


class TestMikroTikGeneratorCapabilityDriven:
    """Tests for capability-driven file generation."""

    def _ctx(self, tmp_path: Path, compiled_json: dict, *, publish_channels: bool = True) -> PluginContext:
        capability_templates = {
            "qos": {"enabled_by": "capabilities.has_qos", "template": "terraform/qos.tf.j2", "output": "qos.tf"},
            "wireguard": {
                "enabled_by": "capabilities.has_wireguard",
                "template": "terraform/vpn.tf.j2",
                "output": "vpn.tf",
            },
            "containers": {
                "enabled_by": "capabilities.has_containers",
                "template": "terraform/containers.tf.j2",
                "output": "containers.tf",
            },
        }
        ctx = PluginContext(
            topology_path="topology/topology.yaml",
            profile="test",
            model_lock={},
            compiled_json=_semanticize(compiled_json),
            output_dir=str(tmp_path / "build"),
            config={
                "generator_artifacts_root": str(tmp_path / "generated"),
                "capability_templates": capability_templates,
            },
        )
        # The generator consumes these from `base.compiler.security_matrix` and
        # derives no substitute. These fixtures are about capability-driven
        # template selection, so they publish the channels empty rather than
        # leave them absent - absence is a blocked generation, which
        # `test_the_generator_blocks_when_the_compiler_published_nothing` covers.
        if publish_channels:
            for key in ("composed_matrices_by_enforcer", "vlan_cidr_map"):
                publish_for_test(ctx, _SECURITY_MATRIX_COMPILER, key, {})
            # capability_flags, wireguard_tunnels, containers, wifi_config,
            # routing_policies, mac_vlan_assignments, bridge_vlans and vlans
            # are likewise required (W07 migration order items 1, 4a, 4b,
            # 4c, 4d, 4e, 4f, 4g). These fixtures test capability-driven
            # template selection itself, so the published values must
            # reflect the fixture's own capabilities/tunnels/containers/
            # wifi/routing-policies/MAC-VLAN/bridge-VLAN/VLAN assignments,
            # not an empty stand-in.
            publish_for_test(
                ctx, _CAPABILITY_FLAGS_COMPILER, "capability_flags", _derive_flags_for_fixture(compiled_json)
            )
            publish_for_test(
                ctx,
                _WIREGUARD_TUNNELS_COMPILER,
                "wireguard_tunnels",
                _derive_wireguard_tunnels_for_fixture(compiled_json),
            )
            publish_for_test(
                ctx,
                _CONTAINERS_COMPILER,
                "containers",
                _derive_containers_for_fixture(compiled_json),
            )
            publish_for_test(
                ctx,
                _WIFI_CONFIG_COMPILER,
                "wifi_config",
                _derive_wifi_config_for_fixture(compiled_json),
            )
            publish_for_test(
                ctx,
                _ROUTING_POLICIES_COMPILER,
                "routing_policies",
                _derive_routing_policies_for_fixture(compiled_json),
            )
            publish_for_test(
                ctx,
                _MAC_VLAN_ASSIGNMENTS_COMPILER,
                "mac_vlan_assignments",
                _derive_mac_vlan_assignments_for_fixture(compiled_json),
            )
            publish_for_test(
                ctx,
                _BRIDGE_VLANS_COMPILER,
                "bridge_vlans",
                _derive_bridge_vlans_for_fixture(compiled_json),
            )
            publish_for_test(
                ctx,
                _VLAN_ENTRIES_COMPILER,
                "vlans",
                _derive_vlans_for_fixture(compiled_json),
            )
        return ctx

    def test_generates_vpn_tf_when_wireguard_capability(self, tmp_path: Path) -> None:
        compiled_json = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-test",
                        "object_ref": "obj.mikrotik.test",
                        "capabilities": ["cap.net.overlay.vpn.wireguard.server"],
                    }
                ],
                "network": [],
                "services": [],
            }
        }
        ctx = self._ctx(tmp_path, compiled_json)
        generator = TerraformMikroTikGenerator("test.generator.mikrotik")

        result = run_plugin_for_test(generator, ctx, Stage.GENERATE, consumes_keys=_CONSUMED_KEYS)

        assert result.status == PluginStatus.SUCCESS
        generated_files = [Path(f).name for f in result.output_data.get("terraform_mikrotik_files", [])]
        assert "vpn.tf" in generated_files

    def test_vpn_tf_has_no_resources_without_wireguard_capability(self, tmp_path: Path) -> None:
        """vpn.tf is always generated but contains no resources when WireGuard is disabled."""
        compiled_json = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-test",
                        "object_ref": "obj.mikrotik.test",
                        # No wireguard capability
                    }
                ],
                "network": [],
                "services": [],
            }
        }
        ctx = self._ctx(tmp_path, compiled_json)
        generator = TerraformMikroTikGenerator("test.generator.mikrotik")

        result = run_plugin_for_test(generator, ctx, Stage.GENERATE, consumes_keys=_CONSUMED_KEYS)

        assert result.status == PluginStatus.SUCCESS
        generated_files = [Path(f).name for f in result.output_data.get("terraform_mikrotik_files", [])]
        # vpn.tf is now a core template, always generated
        assert "vpn.tf" in generated_files
        # But it should NOT contain WireGuard resources when capability is disabled
        vpn_tf = (tmp_path / "generated" / "terraform" / "mikrotik" / "vpn.tf").read_text(encoding="utf-8")
        assert "routeros_interface_wireguard" not in vpn_tf
        assert "WireGuard capability not enabled" in vpn_tf

    def test_generates_containers_tf_for_chateau(self, tmp_path: Path) -> None:
        """Chateau models should generate containers.tf when capability is present."""
        # ADR0078: Capabilities come from object definitions, resolved during compilation
        compiled_json = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-mikrotik-chateau",
                        "object_ref": "obj.mikrotik.chateau_lte7_ax",
                        # These capabilities are defined in obj.mikrotik.chateau_lte7_ax.yaml
                        "enabled_capabilities": [
                            "cap.net.platform.containers",
                        ],
                    }
                ],
                "network": [],
                "services": [],
            }
        }
        ctx = self._ctx(tmp_path, compiled_json)
        generator = TerraformMikroTikGenerator("test.generator.mikrotik")

        result = run_plugin_for_test(generator, ctx, Stage.GENERATE, consumes_keys=_CONSUMED_KEYS)

        assert result.status == PluginStatus.SUCCESS
        generated_files = [Path(f).name for f in result.output_data.get("terraform_mikrotik_files", [])]
        assert "containers.tf" in generated_files

    def test_core_files_always_generated(self, tmp_path: Path) -> None:
        """Core Terraform files should always be generated."""
        compiled_json = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-test",
                        "object_ref": "obj.mikrotik.test",
                    }
                ],
                "network": [],
                "services": [],
            }
        }
        ctx = self._ctx(tmp_path, compiled_json)
        generator = TerraformMikroTikGenerator("test.generator.mikrotik")

        result = run_plugin_for_test(generator, ctx, Stage.GENERATE, consumes_keys=_CONSUMED_KEYS)

        assert result.status == PluginStatus.SUCCESS
        generated_files = [Path(f).name for f in result.output_data.get("terraform_mikrotik_files", [])]
        # Core files should always exist
        assert "provider.tf" in generated_files
        assert "interfaces.tf" in generated_files
        assert "firewall.tf" in generated_files
        assert "variables.tf" in generated_files
        assert "outputs.tf" in generated_files

    def test_the_generator_blocks_when_the_compiler_published_nothing(self, tmp_path: Path) -> None:
        """No channel, no artifacts - and no quiet success.

        The projection used to carry its own derivation of zone membership and
        address-domain CIDRs, so a missing compiler channel rendered an empty
        address list and an empty tunnel route set while the plugin reported
        SUCCESS. Both derivations are gone. This pins the replacement behaviour:
        the run fails, and it names the producer that should have published.

        In the pipeline the kernel refuses to dispatch at all, because the
        manifest declares both keys `required: true` (E8003). This test exercises
        the second guard, the one that holds for any direct caller.
        """
        compiled_json = {
            "instances": {
                "devices": [{"instance_id": "rtr-test", "object_ref": "obj.mikrotik.test"}],
                "network": [],
                "services": [],
            }
        }
        ctx = self._ctx(tmp_path, compiled_json, publish_channels=False)
        generator = TerraformMikroTikGenerator("test.generator.mikrotik")

        result = run_plugin_for_test(generator, ctx, Stage.GENERATE, consumes_keys=_CONSUMED_KEYS)

        assert result.status == PluginStatus.FAILED
        messages = [diagnostic.message for diagnostic in result.diagnostics]
        assert any("base.compiler.security_matrix" in message for message in messages), messages
        assert not list((tmp_path / "generated").rglob("*.tf")), "artifacts were written despite the failure"

    def test_the_manifest_declares_all_ten_channels_required(self) -> None:
        """`required: false` is what let the absence pass as an empty result."""
        import sys as _sys

        _sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "topology-tools"))
        from yaml_loader import load_yaml_file

        manifest_path = Path(__file__).resolve().parents[2] / "topology/object-modules/mikrotik/plugins.yaml"
        manifest = load_yaml_file(manifest_path) or {}
        spec = next(item for item in manifest["plugins"] if item["id"] == "object.mikrotik.generator.terraform")
        consumes = {item["key"]: item for item in spec.get("consumes", [])}

        for key in ("composed_matrices_by_enforcer", "vlan_cidr_map"):
            assert consumes[key]["from_plugin"] == _SECURITY_MATRIX_COMPILER
            assert consumes[key]["required"] is True, f"{key} must block generation when absent"
        # W07 migration order item 1: capability_flags is required the same way.
        assert consumes["capability_flags"]["from_plugin"] == _CAPABILITY_FLAGS_COMPILER
        assert consumes["capability_flags"]["required"] is True
        # W07 migration order item 4a: wireguard_tunnels is required the same way.
        assert consumes["wireguard_tunnels"]["from_plugin"] == _WIREGUARD_TUNNELS_COMPILER
        assert consumes["wireguard_tunnels"]["required"] is True
        # W07 migration order item 4b: containers is required the same way.
        assert consumes["containers"]["from_plugin"] == _CONTAINERS_COMPILER
        assert consumes["containers"]["required"] is True
        # W07 migration order item 4c: wifi_config is required the same way.
        assert consumes["wifi_config"]["from_plugin"] == _WIFI_CONFIG_COMPILER
        assert consumes["wifi_config"]["required"] is True
        # W07 migration order item 4d: routing_policies is required the same way.
        assert consumes["routing_policies"]["from_plugin"] == _ROUTING_POLICIES_COMPILER
        assert consumes["routing_policies"]["required"] is True
        # W07 migration order item 4e: mac_vlan_assignments is required the same way.
        assert consumes["mac_vlan_assignments"]["from_plugin"] == _MAC_VLAN_ASSIGNMENTS_COMPILER
        assert consumes["mac_vlan_assignments"]["required"] is True
        # W07 migration order item 4f: bridge_vlans is required the same way.
        assert consumes["bridge_vlans"]["from_plugin"] == _BRIDGE_VLANS_COMPILER
        assert consumes["bridge_vlans"]["required"] is True
        # W07 migration order item 4g: vlans is required the same way.
        assert consumes["vlans"]["from_plugin"] == _VLAN_ENTRIES_COMPILER
        assert consumes["vlans"]["required"] is True

#!/usr/bin/env python3
"""Integration checks for generator projection helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.object_projection_loader import (  # noqa: E402
    load_bootstrap_projection_module,
    load_object_projection_module,
)
from plugins.generators.projections.ansible import build_ansible_projection  # noqa: E402
from plugins.generators.projections.docs import build_docs_projection  # noqa: E402
from plugins.generators.projections.topology_graph import build_topology_projection  # noqa: E402

_PROXMOX_PROJECTIONS = load_object_projection_module("proxmox")
_MIKROTIK_PROJECTIONS = load_object_projection_module("mikrotik")

import importlib.util as _importlib_util

_CAPABILITY_FLAGS_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "topology"
    / "object-modules"
    / "mikrotik"
    / "plugins"
    / "compilers"
    / "capability_flags_compiler.py"
)
_capability_flags_spec = _importlib_util.spec_from_file_location(
    "test_projection_helpers_capability_flags_compiler", _CAPABILITY_FLAGS_MODULE_PATH
)
_capability_flags_module = _importlib_util.module_from_spec(_capability_flags_spec)
_capability_flags_spec.loader.exec_module(_capability_flags_module)
# W07 migration order item 1: matches what the real compiler derives for zero
# routers (all keys present, all False) - not an empty dict, which the golden
# snapshot and templates do not treat the same way.
_EMPTY_CAPABILITY_FLAGS = _capability_flags_module._derive_capability_flags([])

_WIREGUARD_TUNNELS_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "topology"
    / "object-modules"
    / "mikrotik"
    / "plugins"
    / "compilers"
    / "wireguard_tunnels_compiler.py"
)
_wireguard_tunnels_spec = _importlib_util.spec_from_file_location(
    "test_projection_helpers_wireguard_tunnels_compiler", _WIREGUARD_TUNNELS_MODULE_PATH
)
_wireguard_tunnels_module = _importlib_util.module_from_spec(_wireguard_tunnels_spec)
_wireguard_tunnels_spec.loader.exec_module(_wireguard_tunnels_module)
# W07 migration order item 4a: matches what the real compiler derives for zero
# tunnels (all keys present, empty/default values) - not an empty dict.
_EMPTY_WIREGUARD_TUNNELS = _wireguard_tunnels_module._extract_wireguard_tunnels([], set(), {})

_CONTAINERS_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "topology"
    / "object-modules"
    / "mikrotik"
    / "plugins"
    / "compilers"
    / "containers_compiler.py"
)
_containers_spec = _importlib_util.spec_from_file_location(
    "test_projection_helpers_containers_compiler", _CONTAINERS_MODULE_PATH
)
_containers_module = _importlib_util.module_from_spec(_containers_spec)
_containers_spec.loader.exec_module(_containers_module)
# W07 migration order item 4b: matches what the real compiler derives for zero
# containers - an empty list, which is already the correct empty shape.
_EMPTY_CONTAINERS = _containers_module._extract_containers([], set())

_WIFI_CONFIG_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "topology"
    / "object-modules"
    / "mikrotik"
    / "plugins"
    / "compilers"
    / "wifi_config_compiler.py"
)
_wifi_config_spec = _importlib_util.spec_from_file_location(
    "test_projection_helpers_wifi_config_compiler", _WIFI_CONFIG_MODULE_PATH
)
_wifi_config_module = _importlib_util.module_from_spec(_wifi_config_spec)
_wifi_config_spec.loader.exec_module(_wifi_config_module)
# W07 migration order item 4c: matches what the real compiler derives for zero
# routers (all keys present, empty lists) - not an empty dict.
_EMPTY_WIFI_CONFIG = _wifi_config_module._extract_wifi_config([])

_ROUTING_POLICIES_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "topology"
    / "object-modules"
    / "mikrotik"
    / "plugins"
    / "compilers"
    / "routing_policies_compiler.py"
)
_routing_policies_spec = _importlib_util.spec_from_file_location(
    "test_projection_helpers_routing_policies_compiler", _ROUTING_POLICIES_MODULE_PATH
)
_routing_policies_module = _importlib_util.module_from_spec(_routing_policies_spec)
_routing_policies_spec.loader.exec_module(_routing_policies_module)

_MAC_VLAN_ASSIGNMENTS_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "topology"
    / "object-modules"
    / "mikrotik"
    / "plugins"
    / "compilers"
    / "mac_vlan_assignments_compiler.py"
)
_mac_vlan_assignments_spec = _importlib_util.spec_from_file_location(
    "test_projection_helpers_mac_vlan_assignments_compiler", _MAC_VLAN_ASSIGNMENTS_MODULE_PATH
)
_mac_vlan_assignments_module = _importlib_util.module_from_spec(_mac_vlan_assignments_spec)
_mac_vlan_assignments_spec.loader.exec_module(_mac_vlan_assignments_module)

_BRIDGE_VLANS_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "topology"
    / "object-modules"
    / "mikrotik"
    / "plugins"
    / "compilers"
    / "bridge_vlans_compiler.py"
)
_bridge_vlans_spec = _importlib_util.spec_from_file_location(
    "test_projection_helpers_bridge_vlans_compiler", _BRIDGE_VLANS_MODULE_PATH
)
_bridge_vlans_module = _importlib_util.module_from_spec(_bridge_vlans_spec)
_bridge_vlans_spec.loader.exec_module(_bridge_vlans_module)

_VLAN_ENTRIES_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "topology"
    / "object-modules"
    / "mikrotik"
    / "plugins"
    / "compilers"
    / "vlan_entries_compiler.py"
)
_vlan_entries_spec = _importlib_util.spec_from_file_location(
    "test_projection_helpers_vlan_entries_compiler", _VLAN_ENTRIES_MODULE_PATH
)
_vlan_entries_module = _importlib_util.module_from_spec(_vlan_entries_spec)
_vlan_entries_spec.loader.exec_module(_vlan_entries_module)

_BRIDGE_ENTRIES_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "topology"
    / "object-modules"
    / "mikrotik"
    / "plugins"
    / "compilers"
    / "bridge_entries_compiler.py"
)
_bridge_entries_spec = _importlib_util.spec_from_file_location(
    "test_projection_helpers_bridge_entries_compiler", _BRIDGE_ENTRIES_MODULE_PATH
)
_bridge_entries_module = _importlib_util.module_from_spec(_bridge_entries_spec)
_bridge_entries_spec.loader.exec_module(_bridge_entries_module)

_FIREWALL_ENTRIES_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "topology"
    / "object-modules"
    / "mikrotik"
    / "plugins"
    / "compilers"
    / "firewall_entries_compiler.py"
)
_firewall_entries_spec = _importlib_util.spec_from_file_location(
    "test_projection_helpers_firewall_entries_compiler", _FIREWALL_ENTRIES_MODULE_PATH
)
_firewall_entries_module = _importlib_util.module_from_spec(_firewall_entries_spec)
_firewall_entries_spec.loader.exec_module(_firewall_entries_module)

_BOOTSTRAP_PROJECTIONS = load_bootstrap_projection_module()

ProjectionError = _PROXMOX_PROJECTIONS.ProjectionError
build_proxmox_projection = _PROXMOX_PROJECTIONS.build_proxmox_projection
_raw_build_mikrotik_projection = _MIKROTIK_PROJECTIONS.build_mikrotik_projection


def _mikrotik_routers_and_rows(compiled_json: dict) -> tuple[set[str], list[dict], list[dict], list[dict]]:
    """(router instance ids, router rows, network-group rows, routeros_container-group rows)."""
    instances = compiled_json.get("instances") if isinstance(compiled_json, dict) else None
    if not isinstance(instances, dict):
        return set(), [], [], []
    devices = instances.get("devices", [])
    if not isinstance(devices, list):
        devices = []
    network_rows = instances.get("network", [])
    if not isinstance(network_rows, list):
        network_rows = []
    container_rows = instances.get("routeros_container", [])
    if not isinstance(container_rows, list):
        container_rows = []
    resolved_object_ref = _capability_flags_module._resolved_object_ref
    routers = [
        row for row in devices if isinstance(row, dict) and resolved_object_ref(row).startswith("obj.mikrotik.")
    ]
    router_ids = {row.get("instance_id") for row in routers}
    return (
        {r for r in router_ids if isinstance(r, str) and r},
        routers,
        [r for r in network_rows if isinstance(r, dict)],
        [r for r in container_rows if isinstance(r, dict)],
    )


def _derive_routing_policies_for(compiled_json: dict) -> list[dict]:
    """Same derivation the real compile-stage compiler performs (W07 item 4d).

    Replicates the plugin's own row-selection/managed_by_ref-resolution
    loop, not just a single all-routers call.
    """
    router_ids, _, network_rows, _ = _mikrotik_routers_and_rows(compiled_json)
    default_router_id = next(iter(sorted(router_ids)), "")
    resolved_object_ref = _capability_flags_module._resolved_object_ref
    routing_policies: list[dict] = []
    for row in network_rows:
        object_ref = resolved_object_ref(row)
        if "routing_policy" not in object_ref:
            continue
        inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
        managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
        if not managed_by_ref and len(router_ids) == 1:
            managed_by_ref = default_router_id
        if managed_by_ref in router_ids:
            routing_policies.append(
                _routing_policies_module._build_routing_policy_entry(
                    row, managed_by_ref=managed_by_ref, vlan_cidr_index={}
                )
            )
    return routing_policies


def _derive_mac_vlan_assignments_for(compiled_json: dict) -> list[dict]:
    """Same derivation the real compile-stage compiler performs (W07 item 4e).

    Replicates the plugin's own vlan_id_index-building slice of the shared
    network-row loop, the same discipline item 4d's helper above established.
    """
    router_ids, _, network_rows, _ = _mikrotik_routers_and_rows(compiled_json)
    devices = (
        compiled_json.get("instances", {}).get("devices", [])
        if isinstance(compiled_json.get("instances"), dict)
        else []
    )
    objects_map = compiled_json.get("objects", {})
    if not isinstance(objects_map, dict):
        objects_map = {}
    default_router_id = next(iter(sorted(router_ids)), "")
    vlan_id_index = _mac_vlan_assignments_module._build_vlan_id_index(
        network_rows,
        router_ids=router_ids,
        default_router_id=default_router_id,
        objects_map=objects_map,
    )
    return _mac_vlan_assignments_module._extract_mac_vlan_assignments(
        {"network": network_rows, "devices": [row for row in devices if isinstance(row, dict)]},
        vlan_id_index,
    )


def _derive_bridge_vlans_for(compiled_json: dict) -> list[dict]:
    """Same derivation the real compile-stage compiler performs (W07 item 4f).

    Depends on `wifi_config` (item 4c)'s already-derived datapath/interface
    shape, the same forward dependency the W07 decision document recorded
    when 4c moved.
    """
    _, routers, _, _ = _mikrotik_routers_and_rows(compiled_json)
    wifi_data = _wifi_config_module._extract_wifi_config(routers)
    return _bridge_vlans_module._extract_bridge_vlans(routers, wifi_data)


def _derive_vlans_for(compiled_json: dict) -> list[dict]:
    """Same derivation the real compile-stage compiler performs (W07 item 4g).

    Replicates the plugin's own row-selection/managed_by_ref-resolution
    loop (VLAN branch of the shared network-row loop), the same discipline
    item 4d's helper above established.
    """
    router_ids, _, network_rows, _ = _mikrotik_routers_and_rows(compiled_json)
    objects_map = compiled_json.get("objects", {})
    if not isinstance(objects_map, dict):
        objects_map = {}
    default_router_id = next(iter(sorted(router_ids)), "")
    resolved_object_ref = _capability_flags_module._resolved_object_ref
    vlans: list[dict] = []
    for row in network_rows:
        if not isinstance(row, dict):
            continue
        object_ref = resolved_object_ref(row)
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
            vlans.append(
                _vlan_entries_module._build_vlan_entry(row, managed_by_ref=managed_by_ref, objects_map=objects_map)
            )
    return vlans


def _derive_bridges_for(compiled_json: dict) -> list[dict]:
    """Same derivation the real compile-stage compiler performs (W07 item 4h).

    Replicates the plugin's own row-selection/managed_by_ref-resolution
    loop (bridge branch of the shared network-row loop), the same
    discipline item 4d's helper above established.
    """
    router_ids, _, network_rows, _ = _mikrotik_routers_and_rows(compiled_json)
    objects_map = compiled_json.get("objects", {})
    if not isinstance(objects_map, dict):
        objects_map = {}
    resolved_object_ref = _capability_flags_module._resolved_object_ref
    bridges: list[dict] = []
    for row in network_rows:
        if not isinstance(row, dict):
            continue
        object_ref = resolved_object_ref(row)
        if "bridge" not in object_ref:
            continue
        inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
        managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
        host_ref = str(inst_data.get("host_ref") or "").strip()
        if not managed_by_ref and host_ref in router_ids:
            managed_by_ref = host_ref
        if managed_by_ref in router_ids:
            bridges.append(
                _bridge_entries_module._build_bridge_entry(row, managed_by_ref=managed_by_ref, objects_map=objects_map)
            )
    return bridges


def _derive_firewall_policies_for(compiled_json: dict) -> list[dict]:
    """Same derivation the real compile-stage compiler performs (W07 item 4i).

    Replicates the plugin's own row-selection/managed_by_ref-resolution
    loop over the dedicated `firewall` instance group - its own loop, not a
    shared one, unlike items 4d/4e/4g/4h.
    """
    router_ids, _, _, _ = _mikrotik_routers_and_rows(compiled_json)
    instances = compiled_json.get("instances")
    firewall_rows = instances.get("firewall", []) if isinstance(instances, dict) else []
    if not isinstance(firewall_rows, list):
        firewall_rows = []
    objects_map = compiled_json.get("objects", {})
    if not isinstance(objects_map, dict):
        objects_map = {}
    default_router_id = next(iter(sorted(router_ids)), "")
    resolved_object_ref = _capability_flags_module._resolved_object_ref
    firewall_policies: list[dict] = []
    for row in firewall_rows:
        if not isinstance(row, dict):
            continue
        object_ref = resolved_object_ref(row)
        if "firewall_policy" not in object_ref:
            continue
        inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
        managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
        if not managed_by_ref and len(router_ids) == 1:
            managed_by_ref = default_router_id
        if managed_by_ref in router_ids:
            firewall_policies.append(
                _firewall_entries_module._build_firewall_entry(
                    row, managed_by_ref=managed_by_ref, objects_map=objects_map
                )
            )
    return firewall_policies


def build_mikrotik_projection(compiled_json: dict, **kwargs) -> dict:
    """The compiler's channels are required arguments; these fixtures state them empty.

    `base.compiler.security_matrix` owns zone membership and address-domain CIDRs,
    and the projection derives no substitute. Omitting the argument is an error;
    passing `{}` is a fixture saying it declares no matrices and no domains. A
    test that cares about zone or CIDR content passes a real mapping.

    `capability_flags` (W07 migration order item 1), `wireguard_tunnels`
    (W07 migration order item 4a), `containers` (W07 migration order item
    4b), `wifi_config` (W07 migration order item 4c), `routing_policies`
    (W07 migration order item 4d), `mac_vlan_assignments` (W07 migration
    order item 4e), `bridge_vlans` (W07 migration order item 4f), `vlans`
    (W07 migration order item 4g), `bridges` (W07 migration order item 4h)
    and `firewall_policies` (W07 migration order item 4i) are likewise
    required, and auto-derived here from the fixture's own
    devices/network/container rows the same way the real compile-stage
    compiler plugins would, unless a test passes its own value to exercise a
    specific case - a fixture that builds real
    wifi/wireguard/container/routing-policy instance_data (like
    test_mikrotik_projection_extracts_wifi_interfaces) needs the derived
    content, not an empty stand-in that silently discards it.
    """
    kwargs.setdefault("composed_matrices_by_enforcer", {})
    kwargs.setdefault("vlan_cidr_map", {})
    if "capability_flags" not in kwargs:
        _, routers, _, _ = _mikrotik_routers_and_rows(compiled_json)
        kwargs["capability_flags"] = _capability_flags_module._derive_capability_flags(routers)
    if (
        "wireguard_tunnels" not in kwargs
        or "containers" not in kwargs
        or "wifi_config" not in kwargs
    ):
        router_ids, routers, network_rows, container_rows = _mikrotik_routers_and_rows(compiled_json)
        kwargs.setdefault(
            "wireguard_tunnels",
            _wireguard_tunnels_module._extract_wireguard_tunnels(network_rows, router_ids, {}),
        )
        kwargs.setdefault("containers", _containers_module._extract_containers(container_rows, router_ids))
        kwargs.setdefault("wifi_config", _wifi_config_module._extract_wifi_config(routers))
    if "routing_policies" not in kwargs:
        kwargs["routing_policies"] = _derive_routing_policies_for(compiled_json)
    if "mac_vlan_assignments" not in kwargs:
        kwargs["mac_vlan_assignments"] = _derive_mac_vlan_assignments_for(compiled_json)
    if "bridge_vlans" not in kwargs:
        kwargs["bridge_vlans"] = _derive_bridge_vlans_for(compiled_json)
    if "vlans" not in kwargs:
        kwargs["vlans"] = _derive_vlans_for(compiled_json)
    if "bridges" not in kwargs:
        kwargs["bridges"] = _derive_bridges_for(compiled_json)
    if "firewall_policies" not in kwargs:
        kwargs["firewall_policies"] = _derive_firewall_policies_for(compiled_json)
    return _raw_build_mikrotik_projection(compiled_json, **kwargs)


build_bootstrap_projection = _BOOTSTRAP_PROJECTIONS.build_bootstrap_projection


def _compiled_fixture() -> dict:
    """Compiled JSON fixture with ADR 0106 initialization_contract requirements."""
    return {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-mk",
                    "instance": {
                        "materializes_object": "obj.mikrotik.chateau_lte7_ax",
                        "materializes_class": "class.network.router",
                    },
                    # ADR 0106: initialization_contract + derived capabilities
                    "object": {
                        "initialization_contract": {"mechanism": "netinstall"},
                        "derived_capabilities": ["cap.bootstrap.netinstall"],
                    },
                },
                {
                    "instance_id": "srv-gamayun",
                    "instance": {
                        "materializes_object": "obj.proxmox.ve",
                        "materializes_class": "class.compute.hypervisor.proxmox",
                    },
                    # ADR 0106: initialization_contract + derived capabilities
                    "object": {
                        "initialization_contract": {"mechanism": "unattended_install"},
                        "derived_capabilities": ["cap.bootstrap.unattended"],
                    },
                },
                {
                    "instance_id": "srv-orangepi5",
                    "instance": {
                        "materializes_object": "obj.orangepi.rk3588.debian",
                        "materializes_class": "class.compute.sbc",
                    },
                    # ADR 0106: initialization_contract + derived capabilities
                    "object": {
                        "initialization_contract": {"mechanism": "cloud_init"},
                        "derived_capabilities": ["cap.bootstrap.cloud_init"],
                    },
                },
                {
                    "instance_id": "inst.ethernet_cable.cat5e",
                    "instance": {
                        "materializes_object": "obj.network.ethernet_cable",
                        "materializes_class": "class.network.physical_link",
                    },
                },
            ],
            "lxc": [
                {
                    "instance_id": "lxc-redis",
                    "instance": {
                        "materializes_object": "obj.proxmox.lxc.debian12.redis",
                        "materializes_class": "class.compute.workload.container",
                    },
                },
                {
                    "instance_id": "lxc-grafana",
                    "instance": {
                        "materializes_object": "obj.proxmox.lxc.debian12.base",
                        "materializes_class": "class.compute.workload.container",
                    },
                },
            ],
            "network": [
                {
                    "instance_id": "inst.net.lan",
                    "instance": {
                        "materializes_object": "obj.network.l2_segment",
                        "materializes_class": "class.network.l2_segment",
                    },
                },
                {
                    "instance_id": "inst.net.wan",
                    "instance": {
                        "materializes_object": "obj.network.l2_segment",
                        "materializes_class": "class.network.l2_segment",
                    },
                },
            ],
            "vm": [
                {
                    "instance_id": "vm-analytics",
                    "instance": {
                        "materializes_object": "obj.proxmox.vm.debian12.analytics",
                        "materializes_class": "class.compute.workload.vm",
                    },
                    "instance_data": {"host_ref": "srv-gamayun"},
                    "layer": "L1",
                }
            ],
            "services": [
                {"instance_id": "svc-redis", "runtime": {"target_ref": "lxc-redis"}},
                {"instance_id": "svc-snmp", "runtime": {"target_ref": "rtr-mk"}},
            ],
        }
    }


def test_proxmox_projection_is_stable_and_scoped() -> None:
    projection = build_proxmox_projection(_compiled_fixture())
    assert [row["instance_id"] for row in projection["proxmox_nodes"]] == ["srv-gamayun"]
    assert [row["instance_id"] for row in projection["lxc"]] == ["lxc-grafana", "lxc-redis"]
    assert [row["instance_id"] for row in projection["services"]] == ["svc-redis"]


def test_mikrotik_projection_is_stable_and_scoped() -> None:
    projection = build_mikrotik_projection(_compiled_fixture())
    assert [row["instance_id"] for row in projection["routers"]] == ["rtr-mk"]
    assert [row["instance_id"] for row in projection["networks"]] == ["inst.net.lan", "inst.net.wan"]
    assert [row["instance_id"] for row in projection["services"]] == ["svc-snmp"]


def test_mikrotik_projection_reads_a_two_scope_composed_plan() -> None:
    """The two-scope fixture section 5b/5d called for.

    D-COMP-1..4 are exercised at the compiler in
    tests/plugin_integration/test_security_matrix_compiler.py; this checks the
    other half of the chain - that the projection and generator pass a
    genuinely composed, multi-scope plan through unchanged rather than only
    ever having been driven by a one-scope input. The real topology has
    exactly one enabled scope, so this is the only place that shape is
    exercised until it exists for real.
    """
    payload = _compiled_fixture()
    composed = {
        "rtr-mk": {
            "zones": {
                "inst.trust_zone.user": {"name": "User", "security_level": 3, "isolated": False, "cidrs": ["10.0.10.0/24"]},
                "inst.trust_zone.dmz": {"name": "DMZ", "security_level": 1, "isolated": False, "cidrs": ["10.0.20.0/24"]},
            },
            "matrix": {
                "inst.trust_zone.user": {
                    "inst.trust_zone.user": {"action": "allow", "rule": "R1", "reason": "same zone", "log": False},
                    "inst.trust_zone.dmz": {"action": "allow", "rule": "R3", "reason": "downhill", "log": False},
                },
                "inst.trust_zone.dmz": {
                    "inst.trust_zone.dmz": {"action": "allow", "rule": "R1", "reason": "same zone", "log": False},
                    "inst.trust_zone.user": {"action": "deny", "rule": "R4", "reason": "uphill", "log": True},
                },
            },
            "policy_overrides": [
                {
                    "name": "user-to-dmz-web",
                    "from_zone_ref": "inst.trust_zone.user",
                    "to_zone_ref": "inst.trust_zone.dmz",
                    "action": "accept",
                    "src_vlan_ref": "inst.vlan.user",
                }
            ],
            "scope_ids": ["inst.security_matrix.a", "inst.security_matrix.b"],
        }
    }
    vlan_cidr_map = {"inst.vlan.user": "10.0.10.0/24"}

    projection = build_mikrotik_projection(
        payload,
        composed_matrices_by_enforcer=composed,
        vlan_cidr_map=vlan_cidr_map,
    )

    matrix = projection["security_matrix"]
    assert matrix["instance_id"] == "inst.security_matrix.a, inst.security_matrix.b"
    assert matrix["managed_by_ref"] == "rtr-mk"
    assert set(matrix["zones"].keys()) == {"inst.trust_zone.user", "inst.trust_zone.dmz"}
    assert matrix["matrix"]["inst.trust_zone.dmz"]["inst.trust_zone.user"]["action"] == "deny"
    (override,) = matrix["policy_overrides"]
    assert override["src_address"] == "10.0.10.0/24"
    assert matrix["unresolved_vlan_refs"] == []


def test_mikrotik_projection_refuses_more_than_one_enforced_router() -> None:
    """Counterexample, ENFORCER-AXIS-CONFORMANCE.md section 4: "Two scopes/planes
    on one device; reverse input order" - the accepted second outcome, an
    explicit unsupported-multiplicity diagnostic, since retaining both is
    blocked on V-11/V-12's Terraform state-layout question.

    `_extract_security_matrix` used to silently pick the sorted-first router
    id when `composed_matrices_by_enforcer` held a plan for more than one
    enforcer (V-10). The real topology has exactly one, so this was latent,
    not active - the same "found before it could bite" pattern as W05/N-07.
    """
    payload = _compiled_fixture()
    payload["instances"]["devices"].append(
        {
            "instance_id": "rtr-mk-2",
            "instance": {
                "materializes_object": "obj.mikrotik.chateau_lte7_ax",
                "materializes_class": "class.network.router",
            },
        }
    )
    composed = {
        "rtr-mk": {
            "zones": {"inst.trust_zone.user": {"name": "User", "security_level": 3, "isolated": False, "cidrs": []}},
            "matrix": {},
            "policy_overrides": [],
            "scope_ids": ["inst.security_matrix.a"],
        },
        "rtr-mk-2": {
            "zones": {"inst.trust_zone.guest": {"name": "Guest", "security_level": 1, "isolated": True, "cidrs": []}},
            "matrix": {},
            "policy_overrides": [],
            "scope_ids": ["inst.security_matrix.b"],
        },
    }

    with pytest.raises(ProjectionError, match="more than one"):
        build_mikrotik_projection(
            payload,
            composed_matrices_by_enforcer=composed,
            vlan_cidr_map={},
        )


def test_mikrotik_projection_accepts_a_router_ref_the_type_resolver_would_refuse() -> None:
    """Characterization, ENFORCER-AXIS-CONFORMANCE.md section 4, counterexample
    "Reference names a target with no enforcement capability | Visible
    refusal; a valid instance_ref alone is insufficient" - **currently
    violated**, not a regression test for desired behavior.

    `base.compiler.effective_model` already computes and publishes a
    definitive per-instance verdict (`enforcer_resolution`, D-TYPE-1..3): an
    instance whose object declares no `cap.net.l3.security.firewall.
    zone_policy` (or the compute-side equivalent) is not an enforcer
    candidate and is omitted from it entirely. `build_mikrotik_projection`
    never reads that channel - it has no parameter for it - and decides
    "is this a router" purely by `object_ref.startswith("obj.mikrotik.")`,
    a name-prefix check with no relationship to whether the compiler's own
    resolver would recognize the instance as an enforcer at all.

    This pins the gap with both halves of the same instance shape run
    through their real compilers, not an assumption about what
    `enforcer_resolution` would say: the object below has no
    `enabled_capabilities` at all, so D-TYPE-1 finds no device-kind
    capability and `_resolve_enforcer` returns `None` (the instance is
    omitted from `enforcer_resolution`, confirmed here) - and the same
    instance is still accepted as a router by the projection. Wiring this
    channel into the object-module plugins that build `router_ids` (~10
    files across MikroTik and Proxmox, none of which import
    `enforcer_resolution` today) is deferred as a separate, larger change;
    this test only characterizes the current gap.
    """
    sys.path.insert(0, str(V5_TOOLS))
    from kernel import PluginContext as _EMPluginContext
    from kernel import PluginRegistry as _EMPluginRegistry
    from kernel import PluginStatus as _EMPluginStatus
    from kernel.plugin_base import Stage as _EMStage
    from tests.helpers.plugin_execution import publish_for_test as _em_publish_for_test

    em_registry = _EMPluginRegistry(V5_TOOLS)
    em_registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    em_ctx = _EMPluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml={"version": "5.0.0", "model": "class-object-instance"},
        classes={"class.router": {"class": "class.router", "version": "1.0.0"}},
        objects={
            "obj.mikrotik.no_zone_policy": {
                "object": "obj.mikrotik.no_zone_policy",
                "version": "1.0.0",
                "class_ref": "class.router",
                # No enabled_capabilities at all: no device-kind capability,
                # so D-TYPE-1 finds nothing to gate an enforcer type on.
            }
        },
        config={},
        instance_bindings={"instance_bindings": {"devices": []}},
    )
    _em_publish_for_test(
        em_ctx,
        "base.compiler.instance_rows",
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "rtr-uncapable",
                "layer": "L1",
                "source_id": "rtr-uncapable",
                "class_ref": "class.router",
                "object_ref": "obj.mikrotik.no_zone_policy",
                "status": "modeled",
                "notes": "",
                "runtime": None,
                "firmware_ref": None,
                "os_refs": [],
                "embedded_in": None,
                "extensions": {},
            }
        ],
    )

    em_result = em_registry.execute_plugin("base.compiler.effective_model", em_ctx, _EMStage.COMPILE)
    assert em_result.status == _EMPluginStatus.SUCCESS
    enforcer_resolution = em_result.output_data["enforcer_resolution"]
    # D-TYPE-1: no device-kind capability declared, so this instance is not
    # an enforcer candidate at all - omitted, not present with type=None.
    assert "rtr-uncapable" not in enforcer_resolution

    payload = {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-uncapable",
                    "instance": {
                        "materializes_object": "obj.mikrotik.no_zone_policy",
                        "materializes_class": "class.network.router",
                    },
                }
            ],
            "network": [],
            "services": [],
        }
    }

    projection = build_mikrotik_projection(payload)

    # The counterexample's required result is "Visible refusal; a valid
    # instance_ref alone is insufficient." This is what currently happens
    # instead: the same instance the compiler's own resolver would not
    # recognize as an enforcer is accepted as a router anyway.
    assert [row["instance_id"] for row in projection["routers"]] == ["rtr-uncapable"]


def test_mikrotik_projection_extracts_routing_policies() -> None:
    payload = _compiled_fixture()
    payload["instances"]["network"].append(
        {
            "instance_id": "inst.routing_policy.vpn_germany",
            "instance": {
                "materializes_object": "obj.network.routing_policy.vpn_vlan",
                "materializes_class": "class.network.routing_policy",
            },
            "instance_data": {
                "policy_name": "vpn-germany-routing",
                "enabled": True,
                "managed_by_ref": "rtr-mk",
                "source_match": {"type": "subnet", "value": "192.168.55.0/24"},
                "target_gateway": {"type": "interface", "value": "wg0"},
                "mikrotik_config": {
                    "mangle_rules": [
                        {
                            "chain": "prerouting",
                            "src_address": "192.168.55.0/24",
                            "dst_address": "!192.168.55.0/24",
                            "action": "mark-connection",
                            "new_connection_mark": "vpn-germany",
                            "passthrough": True,
                        },
                        {
                            "chain": "prerouting",
                            "connection_mark": "vpn-germany",
                            "action": "mark-routing",
                            "new_routing_mark": "vpn-tunnel",
                            "passthrough": False,
                        },
                    ],
                    "routing_table": {"name": "vpn-tunnel", "fib": True},
                    "routes": [
                        {"dst_address": "0.0.0.0/0", "gateway": "wg0", "routing_table": "vpn-tunnel"},
                    ],
                },
            },
        }
    )

    projection = build_mikrotik_projection(payload)

    assert projection["counts"]["routing_policies"] == 1
    (policy,) = projection["routing_policies"]
    assert policy["instance_id"] == "inst.routing_policy.vpn_germany"
    assert policy["name"] == "vpn_germany"
    assert policy["policy_name"] == "vpn-germany-routing"
    assert policy["enabled"] is True
    assert policy["source_subnet"] == "192.168.55.0/24"
    assert policy["tunnel_interface"] == "wg0"
    assert policy["routing_table"] == {"name": "vpn-tunnel", "fib": True}
    assert [rule["action"] for rule in policy["mangle_rules"]] == ["mark-connection", "mark-routing"]
    assert policy["routes"][0]["gateway"] == "wg0"
    assert policy["managed_by_ref"] == "rtr-mk"
    # routing_policy objects contain "vlan" in their object ref (obj.network.routing_policy.vpn_vlan)
    # and must not leak into the VLAN projection.
    assert "inst.routing_policy.vpn_germany" not in [vlan.get("instance_id") for vlan in projection["vlans"]]


def test_mikrotik_projection_extracts_wifi_interfaces() -> None:
    payload = _compiled_fixture()
    payload["instances"]["devices"][0]["instance_data"] = {
        "observed_runtime": {
            "wifi": {
                "wifi1": {
                    "ssid": "Home-Main",
                    "mode": "ap",
                    "security": "wpa2-psk",
                    "status": "running",
                },
                "wifi_vpn_germany": {
                    "name": "wifi-vpn-germany",
                    "ssid": "VPN-Germany",
                    "mode": "ap",
                    "security": "wpa2-psk",
                    "master_interface": "wifi1",
                    "status": "bound",
                    "datapath": {"name": "dp-vpn-germany", "bridge": "bridge", "vlan_id": 55},
                },
                "wifi_guest": {
                    "ssid": "Guest",
                    "mode": "ap",
                    "security": "wpa2-psk",
                    "status": "staged",
                },
            }
        }
    }

    projection = build_mikrotik_projection(payload)
    interfaces = projection["wifi"]["interfaces"]

    # Physical radio bound by mapping key, no master_interface.
    assert {"name": "wifi1", "configuration": "cfg-wifi1"} in interfaces
    # Virtual (slave) AP: explicit name + master_interface must be preserved
    # so deploy tooling can create it on a fresh RouterOS.
    assert {
        "name": "wifi-vpn-germany",
        "configuration": "cfg-wifi_vpn_germany",
        "master_interface": "wifi1",
    } in interfaces
    # Staged SSIDs keep their configuration but are never bound to an AP.
    assert "cfg-wifi_guest" in [cfg["name"] for cfg in projection["wifi"]["configurations"]]
    assert "cfg-wifi_guest" not in [row["configuration"] for row in interfaces]


def test_ansible_projection_contains_hosts_from_l1_and_l4() -> None:
    projection = build_ansible_projection(_compiled_fixture())
    assert [row["instance_id"] for row in projection["hosts"]] == [
        "lxc-grafana",
        "lxc-redis",
        "rtr-mk",
        "srv-gamayun",
        "srv-orangepi5",
        "vm-analytics",
    ]
    assert "inst.ethernet_cable.cat5e" not in [row["instance_id"] for row in projection["hosts"]]


def test_bootstrap_projection_selects_target_devices() -> None:
    projection = build_bootstrap_projection(_compiled_fixture())
    assert [row["instance_id"] for row in projection["proxmox_nodes"]] == ["srv-gamayun"]
    assert [row["instance_id"] for row in projection["mikrotik_nodes"]] == ["rtr-mk"]
    assert [row["instance_id"] for row in projection["orangepi_nodes"]] == ["srv-orangepi5"]


def test_ansible_projection_accepts_wave3_lineage_fallback_refs() -> None:
    payload = {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-mk",
                    "instance": {
                        "materializes_object": "obj.mikrotik.chateau_lte7_ax",
                        "materializes_class": "class.network.router",
                    },
                }
            ],
            "lxc": [],
        }
    }
    projection = build_ansible_projection(payload)
    assert [row["instance_id"] for row in projection["hosts"]] == ["rtr-mk"]
    assert projection["hosts"][0]["object_ref"] == "obj.mikrotik.chateau_lte7_ax"


@pytest.mark.parametrize(
    "builder",
    [
        build_proxmox_projection,
        build_mikrotik_projection,
        build_ansible_projection,
        build_bootstrap_projection,
    ],
)
def test_projection_requires_instances_mapping(builder) -> None:
    with pytest.raises(ProjectionError, match="compiled_json.instances must be mapping/object"):
        builder({})


def test_projection_requires_required_fields() -> None:
    payload = _compiled_fixture()
    payload["instances"]["lxc"][0]["instance_id"] = ""
    with pytest.raises(
        ProjectionError,
        match=r"compiled_json\.instances\.lxc\[0\]\.instance_id must be non-empty string",
    ):
        build_proxmox_projection(payload)


def test_docs_projection_includes_service_dependencies() -> None:
    """Test that build_docs_projection extracts service dependencies with safe_id."""
    payload = {
        "instances": {
            "devices": [],
            "lxc": [],
            "services": [
                {
                    "instance_id": "svc-grafana@lxc.lxc-grafana",
                    "instance": {
                        "materializes_object": "obj.service.grafana",
                        "materializes_class": "class.service.visualization",
                    },
                    "instance_data": {
                        "dependencies": [
                            {"service_ref": "svc-prometheus@lxc.lxc-prometheus"},
                        ],
                    },
                },
                {
                    "instance_id": "svc-prometheus@lxc.lxc-prometheus",
                    "instance": {
                        "materializes_object": "obj.service.prometheus",
                        "materializes_class": "class.service.monitoring",
                    },
                    "instance_data": {},
                },
            ],
            "network": [],
        }
    }

    projection = build_docs_projection(payload)

    assert "service_dependencies" in projection
    deps = projection["service_dependencies"]
    assert len(deps) == 1
    assert deps[0]["service_id"] == "svc-grafana@lxc.lxc-grafana"
    assert deps[0]["depends_on"] == "svc-prometheus@lxc.lxc-prometheus"
    assert deps[0]["service_safe_id"] == "svc_grafana_lxc_lxc_grafana"
    assert deps[0]["depends_on_safe_id"] == "svc_prometheus_lxc_lxc_prometheus"


def test_docs_projection_includes_vms_with_host_ref() -> None:
    payload = {
        "instances": {
            "devices": [],
            "lxc": [],
            "services": [],
            "network": [],
            "vm": [
                {
                    "instance_id": "vm-analytics",
                    "instance": {
                        "materializes_object": "obj.proxmox.vm.debian12.analytics",
                        "materializes_class": "class.compute.workload.vm",
                    },
                    "instance_data": {"host_ref": "srv-gamayun"},
                }
            ],
        }
    }

    projection = build_docs_projection(payload)

    assert "vms" in projection
    assert len(projection["vms"]) == 1
    assert projection["vms"][0]["instance_id"] == "vm-analytics"
    assert projection["vms"][0]["host_ref"] == "srv-gamayun"


def test_safe_id_sanitizes_special_characters() -> None:
    """Test that safe_id replaces '.', '-', and '@' with '_'."""
    from plugins.generators.projections.mermaid import _safe_id

    assert _safe_id("svc-grafana@lxc.lxc-grafana") == "svc_grafana_lxc_lxc_grafana"
    assert _safe_id("inst.vlan.servers") == "inst_vlan_servers"
    assert _safe_id("rtr-mikrotik-chateau") == "rtr_mikrotik_chateau"
    assert _safe_id("svc-redis") == "svc_redis"
    assert _safe_id("simple") == "simple"


def test_topology_projection_contains_cross_domain_nodes_and_edges() -> None:
    payload = {
        "instances": {
            "devices": [
                {
                    "instance_id": "srv-gamayun",
                    "instance": {
                        "materializes_object": "obj.proxmox.ve",
                        "materializes_class": "class.compute.hypervisor.proxmox",
                    },
                    "layer": "L1",
                }
            ],
            "lxc": [
                {
                    "instance_id": "lxc-grafana",
                    "instance": {
                        "materializes_object": "obj.proxmox.lxc.debian12.base",
                        "materializes_class": "class.compute.workload.container",
                    },
                    "instance_data": {"host_ref": "srv-gamayun"},
                    "layer": "L1",
                }
            ],
            "vm": [
                {
                    "instance_id": "vm-analytics",
                    "instance": {
                        "materializes_object": "obj.proxmox.vm.debian12.analytics",
                        "materializes_class": "class.compute.workload.vm",
                    },
                    "instance_data": {"host_ref": "srv-gamayun"},
                    "layer": "L1",
                }
            ],
            "services": [
                {
                    "instance_id": "svc-grafana",
                    "instance": {
                        "materializes_object": "obj.service.grafana",
                        "materializes_class": "class.service.visualization",
                    },
                    "runtime": {"target_ref": "lxc-grafana", "network_binding_ref": "inst.vlan.servers"},
                    "instance_data": {"dependencies": [{"service_ref": "svc-prometheus"}]},
                    "layer": "L4",
                },
                {
                    "instance_id": "svc-prometheus",
                    "instance": {
                        "materializes_object": "obj.service.prometheus",
                        "materializes_class": "class.service.monitoring",
                    },
                    "runtime": {"target_ref": "lxc-grafana"},
                    "instance_data": {},
                    "layer": "L4",
                },
            ],
            "network": [
                {
                    "instance_id": "inst.trust_zone.servers",
                    "instance": {
                        "materializes_object": "obj.network.trust_zone.servers",
                        "materializes_class": "class.network.trust_zone",
                    },
                },
                {
                    "instance_id": "inst.vlan.servers",
                    "instance": {
                        "materializes_object": "obj.network.vlan.servers",
                        "materializes_class": "class.network.vlan",
                    },
                    "instance_data": {
                        "managed_by_ref": "srv-gamayun",
                        "trust_zone_ref": "inst.trust_zone.servers",
                    },
                },
            ],
            "pools": [
                {
                    "instance_id": "inst.pool.fast",
                    "instance": {
                        "materializes_object": "obj.storage.pool.fast",
                        "materializes_class": "class.storage.pool.zfs",
                    },
                    "instance_data": {"host_ref": "srv-gamayun"},
                }
            ],
            "data-assets": [
                {
                    "instance_id": "inst.data.asset.monitoring",
                    "instance": {
                        "materializes_object": "obj.storage.data_asset.monitoring",
                        "materializes_class": "class.storage.data_asset",
                    },
                    "instance_data": {"host_ref": "srv-gamayun"},
                }
            ],
            "operations": [
                {
                    "instance_id": "inst.backup.monitoring",
                    "instance": {
                        "materializes_object": "obj.ops.backup",
                        "materializes_class": "class.ops.backup_policy",
                    },
                    "instance_data": {
                        "target_ref": "svc-grafana",
                        "data_asset_ref": "inst.data.asset.monitoring",
                        "storage_ref": "inst.pool.fast",
                    },
                }
            ],
            "observability": [],
            "firewall": [],
            "power": [],
            "qos": [],
        }
    }

    projection = build_topology_projection(payload)
    nodes = projection["nodes"]
    edges = projection["edges"]
    metadata = projection["metadata"]
    assert any(row["instance_id"] == "srv-gamayun" and row["domain"] == "physical" for row in nodes)
    assert any(row["instance_id"] == "vm-analytics" and row["node_type"] == "vm" for row in nodes)
    assert any(row["instance_id"] == "svc-grafana" and row["domain"] == "services" for row in nodes)
    assert any(row["instance_id"] == "inst.vlan.servers" and row["domain"] == "network" for row in nodes)
    assert any(row["instance_id"] == "inst.pool.fast" and row["domain"] == "storage" for row in nodes)
    assert any(row["instance_id"] == "inst.backup.monitoring" and row["domain"] == "operations" for row in nodes)

    edge_tuples = {(row["source_id"], row["target_id"], row["edge_type"]) for row in edges}
    assert ("lxc-grafana", "srv-gamayun", "hosted_on") in edge_tuples
    assert ("vm-analytics", "srv-gamayun", "hosted_on") in edge_tuples
    assert ("svc-grafana", "svc-prometheus", "service_dependency") in edge_tuples
    assert ("svc-grafana", "lxc-grafana", "runtime_target") in edge_tuples
    assert ("svc-grafana", "inst.vlan.servers", "runtime_network_binding") in edge_tuples
    assert ("inst.vlan.servers", "srv-gamayun", "managed_by") in edge_tuples
    assert ("inst.backup.monitoring", "inst.pool.fast", "writes_to_storage") in edge_tuples
    assert metadata["node_type_counts"].get("service", 0) >= 2
    assert metadata["edge_type_counts"].get("service_dependency", 0) >= 1
    assert metadata["domain_counts"].get("services", 0) >= 2
    assert metadata["layer_counts"].get("L4", 0) >= 2


def test_topology_projection_materializes_external_nodes_for_edge_endpoints() -> None:
    payload = {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-main",
                    "instance": {
                        "materializes_object": "obj.network.router.main",
                        "materializes_class": "class.network.router",
                    },
                }
            ],
            "network": [
                {
                    "instance_id": "inst.data_link.wan",
                    "instance": {
                        "materializes_object": "obj.network.data_link.wan",
                        "materializes_class": "class.network.data_link",
                    },
                    "instance_data": {
                        "endpoint_a": {"device_ref": "rtr-main"},
                        "endpoint_b": {"external_ref": "external.internet"},
                    },
                }
            ],
            "services": [],
            "lxc": [],
            "vm": [],
            "pools": [],
            "data-assets": [],
            "operations": [],
            "observability": [],
            "firewall": [],
            "power": [],
            "qos": [],
        }
    }

    projection = build_topology_projection(payload)
    nodes = projection["nodes"]
    edges = projection["edges"]
    metadata = projection["metadata"]

    assert any(row["instance_id"] == "external.internet" and row["node_type"] == "external_ref" for row in nodes)
    assert ("rtr-main", "external.internet", "data_link") in {
        (row["source_id"], row["target_id"], row["edge_type"]) for row in edges
    }
    assert metadata["node_type_counts"].get("external_ref", 0) >= 1

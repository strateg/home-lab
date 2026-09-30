"""The channels the MikroTik generator consumes, for tests that render it.

`object.mikrotik.generator.terraform` consumes `composed_matrices_by_enforcer`
and `vlan_cidr_map` from `base.compiler.security_matrix`, both declared
`required: true`. `composed_matrices_by_enforcer` replaced `security_matrices`
(ADR 0118-analysis/ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md sections 5c/5d,
N-07): the projection used to re-derive R1-R6 itself and now reads the
compiler's already-composed plan per enforcer instead. The projection derives
no substitute for either channel, so a test that runs the generator has to say
what they hold - an omission is a blocked run, which is the point of the
contract and is covered by its own negative test.

It also consumes `capability_flags` from `object.mikrotik.compiler.
capability_flags` (W07 migration order item 1, 2026-09-29),
`wireguard_tunnels` from `object.mikrotik.compiler.wireguard_tunnels` (W07
migration order item 4a, 2026-09-29), `containers` from `object.mikrotik.
compiler.containers` (W07 migration order item 4b, 2026-09-29),
`wifi_config` from `object.mikrotik.compiler.wifi_config` (W07 migration
order item 4c, 2026-09-29), `routing_policies` from `object.mikrotik.
compiler.routing_policies` (W07 migration order item 4d, 2026-09-29) and
`mac_vlan_assignments` from `object.mikrotik.compiler.mac_vlan_assignments`
(W07 migration order item 4e, 2026-09-29), `bridge_vlans` from
`object.mikrotik.compiler.bridge_vlans` (W07 migration order item 4f,
2026-09-29), `vlans` from `object.mikrotik.compiler.vlan_entries` (W07
migration order item 4g, 2026-09-29), `bridges` from `object.mikrotik.
compiler.bridge_entries` (W07 migration order item 4h, 2026-09-29) and
`firewall_policies` from `object.mikrotik.compiler.firewall_entries` (W07
migration order item 4i, 2026-09-30), all ten likewise `required: true`.
Unlike the matrix/CIDR pair, these ten are not published empty: capability-,
tunnel-, container-, wifi-, routing-policy-, MAC-VLAN-, bridge-VLAN-,
VLAN-, bridge- and firewall-policy-driven tests need them to reflect the
fixture's own routers, so `publish_empty_channels` derives all ten from
`ctx.compiled_json` the same way the real compile-stage plugins do.

These helpers make the statement one line. Passing empty mappings for the
matrix/CIDR channels means "this fixture declares no matrices and no address
domains", which is true of every fixture that is about template selection,
host derivation or file inventory rather than about zone content.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path as _Path
from typing import Any

SECURITY_MATRIX_COMPILER = "base.compiler.security_matrix"
EFFECTIVE_MODEL_COMPILER = "base.compiler.effective_model"
CAPABILITY_FLAGS_COMPILER = "object.mikrotik.compiler.capability_flags"
WIREGUARD_TUNNELS_COMPILER = "object.mikrotik.compiler.wireguard_tunnels"
CONTAINERS_COMPILER = "object.mikrotik.compiler.containers"
WIFI_CONFIG_COMPILER = "object.mikrotik.compiler.wifi_config"
ROUTING_POLICIES_COMPILER = "object.mikrotik.compiler.routing_policies"
MAC_VLAN_ASSIGNMENTS_COMPILER = "object.mikrotik.compiler.mac_vlan_assignments"
BRIDGE_VLANS_COMPILER = "object.mikrotik.compiler.bridge_vlans"
VLAN_ENTRIES_COMPILER = "object.mikrotik.compiler.vlan_entries"
BRIDGE_ENTRIES_COMPILER = "object.mikrotik.compiler.bridge_entries"
FIREWALL_ENTRIES_COMPILER = "object.mikrotik.compiler.firewall_entries"
CHANNEL_KEYS = ("composed_matrices_by_enforcer", "vlan_cidr_map")


def _load_module(entry_filename: str, class_or_func_owner_label: str):
    module_path = (
        _Path(__file__).resolve().parents[2]
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "compilers"
        / entry_filename
    )
    spec = importlib.util.spec_from_file_location(
        f"mikrotik_security_channels_{class_or_func_owner_label}", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CAPABILITY_FLAGS_MODULE = _load_module("capability_flags_compiler.py", "capability_flags")
_EMPTY_CAPABILITY_FLAGS = _CAPABILITY_FLAGS_MODULE._derive_capability_flags([])

_WIREGUARD_TUNNELS_MODULE = _load_module("wireguard_tunnels_compiler.py", "wireguard_tunnels")
_EMPTY_WIREGUARD_TUNNELS = _WIREGUARD_TUNNELS_MODULE._extract_wireguard_tunnels([], set(), {})

_CONTAINERS_MODULE = _load_module("containers_compiler.py", "containers")
_EMPTY_CONTAINERS = _CONTAINERS_MODULE._extract_containers([], set())

_WIFI_CONFIG_MODULE = _load_module("wifi_config_compiler.py", "wifi_config")
_EMPTY_WIFI_CONFIG = _WIFI_CONFIG_MODULE._extract_wifi_config([])

_ROUTING_POLICIES_MODULE = _load_module("routing_policies_compiler.py", "routing_policies")
_EMPTY_ROUTING_POLICIES: list[dict[str, Any]] = []

_MAC_VLAN_ASSIGNMENTS_MODULE = _load_module("mac_vlan_assignments_compiler.py", "mac_vlan_assignments")
_EMPTY_MAC_VLAN_ASSIGNMENTS: list[dict[str, Any]] = []

_BRIDGE_VLANS_MODULE = _load_module("bridge_vlans_compiler.py", "bridge_vlans")
_EMPTY_BRIDGE_VLANS: list[dict[str, Any]] = []

_VLAN_ENTRIES_MODULE = _load_module("vlan_entries_compiler.py", "vlan_entries")
_EMPTY_VLANS: list[dict[str, Any]] = []

_BRIDGE_ENTRIES_MODULE = _load_module("bridge_entries_compiler.py", "bridge_entries")
_EMPTY_BRIDGES: list[dict[str, Any]] = []

_FIREWALL_ENTRIES_MODULE = _load_module("firewall_entries_compiler.py", "firewall_entries")
_EMPTY_FIREWALL_POLICIES: list[dict[str, Any]] = []


def _mikrotik_router_ids(
    compiled_json: Any,
) -> tuple[set[str], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """(router instance ids, router rows, network-group rows, routeros_container-group rows)."""
    if not isinstance(compiled_json, dict):
        return set(), [], [], []
    instances = compiled_json.get("instances")
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
    resolved_object_ref = _CAPABILITY_FLAGS_MODULE._resolved_object_ref
    router_ids: set[str] = set()
    routers: list[dict[str, Any]] = []
    for row in devices:
        if not isinstance(row, dict) or not resolved_object_ref(row).startswith("obj.mikrotik."):
            continue
        routers.append(row)
        instance_id = row.get("instance_id")
        if isinstance(instance_id, str) and instance_id:
            router_ids.add(instance_id)
    return router_ids, routers, network_rows, container_rows


def _mikrotik_objects_map(compiled_json: Any) -> dict[str, Any]:
    """The objects map compiled_json carries, for MAC-VLAN's vlan_id fallback."""
    if not isinstance(compiled_json, dict):
        return {}
    objects_map = compiled_json.get("objects")
    return objects_map if isinstance(objects_map, dict) else {}


def _derive_capability_flags_for(compiled_json: Any) -> dict[str, bool]:
    """Same derivation the real compile-stage compiler performs (W07 item 1)."""
    if not isinstance(compiled_json, dict):
        return dict(_EMPTY_CAPABILITY_FLAGS)
    instances = compiled_json.get("instances", {})
    devices = instances.get("devices", []) if isinstance(instances, dict) else []
    resolved_object_ref = _CAPABILITY_FLAGS_MODULE._resolved_object_ref
    routers = [
        row for row in devices if isinstance(row, dict) and resolved_object_ref(row).startswith("obj.mikrotik.")
    ]
    return _CAPABILITY_FLAGS_MODULE._derive_capability_flags(routers)


def _derive_wireguard_tunnels_for(compiled_json: Any) -> dict[str, Any]:
    """Same derivation the real compile-stage compiler performs (W07 item 4a)."""
    if not isinstance(compiled_json, dict):
        return dict(_EMPTY_WIREGUARD_TUNNELS)
    router_ids, _, network_rows, _ = _mikrotik_router_ids(compiled_json)
    return _WIREGUARD_TUNNELS_MODULE._extract_wireguard_tunnels(network_rows, router_ids, {})


def _derive_containers_for(compiled_json: Any) -> list[dict[str, Any]]:
    """Same derivation the real compile-stage compiler performs (W07 item 4b)."""
    if not isinstance(compiled_json, dict):
        return list(_EMPTY_CONTAINERS)
    router_ids, _, _, container_rows = _mikrotik_router_ids(compiled_json)
    return _CONTAINERS_MODULE._extract_containers(container_rows, router_ids)


def _derive_wifi_config_for(compiled_json: Any) -> dict[str, Any]:
    """Same derivation the real compile-stage compiler performs (W07 item 4c)."""
    if not isinstance(compiled_json, dict):
        return dict(_EMPTY_WIFI_CONFIG)
    _, routers, _, _ = _mikrotik_router_ids(compiled_json)
    return _WIFI_CONFIG_MODULE._extract_wifi_config(routers)


def _derive_routing_policies_for(compiled_json: Any) -> list[dict[str, Any]]:
    """Same derivation the real compile-stage compiler performs (W07 item 4d).

    Replicates the plugin's own row-selection/managed_by_ref-resolution
    loop, not just a single all-routers call - routing policies are built
    per qualifying network row, not from the router list as a whole.
    """
    if not isinstance(compiled_json, dict):
        return list(_EMPTY_ROUTING_POLICIES)
    router_ids, _, network_rows, _ = _mikrotik_router_ids(compiled_json)
    default_router_id = next(iter(sorted(router_ids)), "")
    resolved_object_ref = _CAPABILITY_FLAGS_MODULE._resolved_object_ref
    routing_policies: list[dict[str, Any]] = []
    for row in network_rows:
        if not isinstance(row, dict):
            continue
        object_ref = resolved_object_ref(row)
        if "routing_policy" not in object_ref:
            continue
        inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
        managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
        if not managed_by_ref and len(router_ids) == 1:
            managed_by_ref = default_router_id
        if managed_by_ref in router_ids:
            routing_policies.append(
                _ROUTING_POLICIES_MODULE._build_routing_policy_entry(
                    row, managed_by_ref=managed_by_ref, vlan_cidr_index={}
                )
            )
    return routing_policies


def _derive_mac_vlan_assignments_for(compiled_json: Any) -> list[dict[str, Any]]:
    """Same derivation the real compile-stage compiler performs (W07 item 4e).

    Replicates the plugin's own vlan_id_index-building slice of the
    shared network-row loop (row-selection, managed_by_ref resolution and the
    vlan_id fallback to object properties), the same discipline item 4d's
    helper above established for a per-row builder fed by a shared loop.
    """
    if not isinstance(compiled_json, dict):
        return list(_EMPTY_MAC_VLAN_ASSIGNMENTS)
    router_ids, _, network_rows, _ = _mikrotik_router_ids(compiled_json)
    objects_map = _mikrotik_objects_map(compiled_json)
    default_router_id = next(iter(sorted(router_ids)), "")
    vlan_id_index = _MAC_VLAN_ASSIGNMENTS_MODULE._build_vlan_id_index(
        network_rows,
        router_ids=router_ids,
        default_router_id=default_router_id,
        objects_map=objects_map,
    )
    devices = compiled_json.get("instances", {}).get("devices", []) if isinstance(compiled_json.get("instances"), dict) else []
    return _MAC_VLAN_ASSIGNMENTS_MODULE._extract_mac_vlan_assignments(
        {"network": network_rows, "devices": devices if isinstance(devices, list) else []},
        vlan_id_index,
    )


def _derive_bridge_vlans_for(compiled_json: Any) -> list[dict[str, Any]]:
    """Same derivation the real compile-stage compiler performs (W07 item 4f).

    Depends on `wifi_config` (item 4c)'s already-derived datapath/interface
    shape, the same forward dependency the W07 decision document recorded
    when 4c moved.
    """
    if not isinstance(compiled_json, dict):
        return list(_EMPTY_BRIDGE_VLANS)
    _, routers, _, _ = _mikrotik_router_ids(compiled_json)
    wifi_data = _derive_wifi_config_for(compiled_json)
    return _BRIDGE_VLANS_MODULE._extract_bridge_vlans(routers, wifi_data)


def _derive_vlans_for(compiled_json: Any) -> list[dict[str, Any]]:
    """Same derivation the real compile-stage compiler performs (W07 item 4g).

    Replicates the plugin's own row-selection/managed_by_ref-resolution
    loop (VLAN branch of the shared network-row loop), the same discipline
    item 4d's helper above established.
    """
    if not isinstance(compiled_json, dict):
        return list(_EMPTY_VLANS)
    router_ids, _, network_rows, _ = _mikrotik_router_ids(compiled_json)
    objects_map = _mikrotik_objects_map(compiled_json)
    default_router_id = next(iter(sorted(router_ids)), "")
    resolved_object_ref = _CAPABILITY_FLAGS_MODULE._resolved_object_ref
    vlans: list[dict[str, Any]] = []
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
                _VLAN_ENTRIES_MODULE._build_vlan_entry(row, managed_by_ref=managed_by_ref, objects_map=objects_map)
            )
    return vlans


def _derive_bridges_for(compiled_json: Any) -> list[dict[str, Any]]:
    """Same derivation the real compile-stage compiler performs (W07 item 4h).

    Replicates the plugin's own row-selection/managed_by_ref-resolution
    loop (bridge branch of the shared network-row loop), the same
    discipline item 4d's helper above established.
    """
    if not isinstance(compiled_json, dict):
        return list(_EMPTY_BRIDGES)
    router_ids, _, network_rows, _ = _mikrotik_router_ids(compiled_json)
    objects_map = _mikrotik_objects_map(compiled_json)
    resolved_object_ref = _CAPABILITY_FLAGS_MODULE._resolved_object_ref
    bridges: list[dict[str, Any]] = []
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
                _BRIDGE_ENTRIES_MODULE._build_bridge_entry(row, managed_by_ref=managed_by_ref, objects_map=objects_map)
            )
    return bridges


def _derive_firewall_policies_for(compiled_json: Any) -> list[dict[str, Any]]:
    """Same derivation the real compile-stage compiler performs (W07 item 4i).

    Replicates the plugin's own row-selection/managed_by_ref-resolution
    loop over the dedicated `firewall` instance group - its own loop, not a
    shared one, unlike items 4d/4e/4g/4h.
    """
    if not isinstance(compiled_json, dict):
        return list(_EMPTY_FIREWALL_POLICIES)
    router_ids, _, _, _ = _mikrotik_router_ids(compiled_json)
    objects_map = _mikrotik_objects_map(compiled_json)
    instances = compiled_json.get("instances")
    firewall_rows = instances.get("firewall", []) if isinstance(instances, dict) else []
    if not isinstance(firewall_rows, list):
        firewall_rows = []
    default_router_id = next(iter(sorted(router_ids)), "")
    resolved_object_ref = _CAPABILITY_FLAGS_MODULE._resolved_object_ref
    firewall_policies: list[dict[str, Any]] = []
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
                _FIREWALL_ENTRIES_MODULE._build_firewall_entry(
                    row, managed_by_ref=managed_by_ref, objects_map=objects_map
                )
            )
    return firewall_policies


def _derive_enforcer_resolution_for(compiled_json: Any) -> dict[str, Any]:
    """V-14 (ENFORCER-AXIS-CONFORMANCE.md): the same resolution the real
    `base.compiler.effective_model` would publish for each name-prefix
    router this helper module already identifies, so callers that derive
    the other ten channels from a fixture's real devices keep picking the
    same routers now that `build_mikrotik_projection` and the ten
    compile-stage compilers select by `enforcer_resolution`'s adapter
    instead of by `object_ref` name prefix.
    """
    router_ids, _, _, _ = _mikrotik_router_ids(compiled_json)
    return {
        router_id: {"type": "network", "adapter": "cap.firewall.security_matrix.routeros"}
        for router_id in router_ids
    }


def publish_empty_channels(ctx: Any) -> None:
    """Publish the matrix/CIDR channels empty, and capability_flags/
    wireguard_tunnels/containers/wifi_config/routing_policies/
    mac_vlan_assignments/bridge_vlans/vlans/bridges/firewall_policies
    derived from `ctx.compiled_json` (empty input still produces the full
    shape the real compilers would, not a bare `{}`/`[]`, so golden-snapshot
    and template-selection fixtures compare equal to production output)."""
    from tests.helpers.plugin_execution import publish_for_test

    for key in CHANNEL_KEYS:
        publish_for_test(ctx, SECURITY_MATRIX_COMPILER, key, {})
    compiled_json = getattr(ctx, "compiled_json", None)
    publish_for_test(
        ctx, EFFECTIVE_MODEL_COMPILER, "enforcer_resolution", _derive_enforcer_resolution_for(compiled_json)
    )
    publish_for_test(
        ctx, CAPABILITY_FLAGS_COMPILER, "capability_flags", _derive_capability_flags_for(compiled_json)
    )
    publish_for_test(
        ctx, WIREGUARD_TUNNELS_COMPILER, "wireguard_tunnels", _derive_wireguard_tunnels_for(compiled_json)
    )
    publish_for_test(ctx, CONTAINERS_COMPILER, "containers", _derive_containers_for(compiled_json))
    publish_for_test(ctx, WIFI_CONFIG_COMPILER, "wifi_config", _derive_wifi_config_for(compiled_json))
    publish_for_test(
        ctx, ROUTING_POLICIES_COMPILER, "routing_policies", _derive_routing_policies_for(compiled_json)
    )
    publish_for_test(
        ctx,
        MAC_VLAN_ASSIGNMENTS_COMPILER,
        "mac_vlan_assignments",
        _derive_mac_vlan_assignments_for(compiled_json),
    )
    publish_for_test(
        ctx, BRIDGE_VLANS_COMPILER, "bridge_vlans", _derive_bridge_vlans_for(compiled_json)
    )
    publish_for_test(ctx, VLAN_ENTRIES_COMPILER, "vlans", _derive_vlans_for(compiled_json))
    publish_for_test(ctx, BRIDGE_ENTRIES_COMPILER, "bridges", _derive_bridges_for(compiled_json))
    publish_for_test(
        ctx, FIREWALL_ENTRIES_COMPILER, "firewall_policies", _derive_firewall_policies_for(compiled_json)
    )


def empty_channel_subscriptions() -> dict[tuple[str, str], Any]:
    """The same, as the `subscriptions` mapping of a `PluginInputSnapshot`.

    No `compiled_json` is available at this call site, so `capability_flags`,
    `wireguard_tunnels`, `containers`, `wifi_config`, `routing_policies`,
    `mac_vlan_assignments`, `bridge_vlans`, `vlans`, `bridges` and
    `firewall_policies` are the all-empty defaults rather than a per-fixture
    derivation.
    """
    from kernel.plugin_base import SubscriptionValue

    subscriptions = {
        (SECURITY_MATRIX_COMPILER, key): SubscriptionValue(from_plugin=SECURITY_MATRIX_COMPILER, key=key, value={})
        for key in CHANNEL_KEYS
    }
    subscriptions[(EFFECTIVE_MODEL_COMPILER, "enforcer_resolution")] = SubscriptionValue(
        from_plugin=EFFECTIVE_MODEL_COMPILER, key="enforcer_resolution", value={}
    )
    subscriptions[(CAPABILITY_FLAGS_COMPILER, "capability_flags")] = SubscriptionValue(
        from_plugin=CAPABILITY_FLAGS_COMPILER, key="capability_flags", value=dict(_EMPTY_CAPABILITY_FLAGS)
    )
    subscriptions[(WIREGUARD_TUNNELS_COMPILER, "wireguard_tunnels")] = SubscriptionValue(
        from_plugin=WIREGUARD_TUNNELS_COMPILER, key="wireguard_tunnels", value=dict(_EMPTY_WIREGUARD_TUNNELS)
    )
    subscriptions[(CONTAINERS_COMPILER, "containers")] = SubscriptionValue(
        from_plugin=CONTAINERS_COMPILER, key="containers", value=list(_EMPTY_CONTAINERS)
    )
    subscriptions[(WIFI_CONFIG_COMPILER, "wifi_config")] = SubscriptionValue(
        from_plugin=WIFI_CONFIG_COMPILER, key="wifi_config", value=dict(_EMPTY_WIFI_CONFIG)
    )
    subscriptions[(ROUTING_POLICIES_COMPILER, "routing_policies")] = SubscriptionValue(
        from_plugin=ROUTING_POLICIES_COMPILER, key="routing_policies", value=list(_EMPTY_ROUTING_POLICIES)
    )
    subscriptions[(MAC_VLAN_ASSIGNMENTS_COMPILER, "mac_vlan_assignments")] = SubscriptionValue(
        from_plugin=MAC_VLAN_ASSIGNMENTS_COMPILER,
        key="mac_vlan_assignments",
        value=list(_EMPTY_MAC_VLAN_ASSIGNMENTS),
    )
    subscriptions[(BRIDGE_VLANS_COMPILER, "bridge_vlans")] = SubscriptionValue(
        from_plugin=BRIDGE_VLANS_COMPILER, key="bridge_vlans", value=list(_EMPTY_BRIDGE_VLANS)
    )
    subscriptions[(VLAN_ENTRIES_COMPILER, "vlans")] = SubscriptionValue(
        from_plugin=VLAN_ENTRIES_COMPILER, key="vlans", value=list(_EMPTY_VLANS)
    )
    subscriptions[(BRIDGE_ENTRIES_COMPILER, "bridges")] = SubscriptionValue(
        from_plugin=BRIDGE_ENTRIES_COMPILER, key="bridges", value=list(_EMPTY_BRIDGES)
    )
    subscriptions[(FIREWALL_ENTRIES_COMPILER, "firewall_policies")] = SubscriptionValue(
        from_plugin=FIREWALL_ENTRIES_COMPILER, key="firewall_policies", value=list(_EMPTY_FIREWALL_POLICIES)
    )
    return subscriptions


def derived_channel_subscriptions(compiled_json: Any) -> dict[tuple[str, str], Any]:
    """Same shape as `empty_channel_subscriptions`, but each of the ten
    non-matrix/CIDR channels is derived from `compiled_json` the same way
    `publish_empty_channels` derives them for a `PluginContext`.

    For tests that build a `PluginInputSnapshot` directly (no `ctx` to
    publish through) and whose fixture carries real capability/tunnel/
    container/wifi/routing-policy/MAC-VLAN/bridge-VLAN/VLAN content the
    assertions depend on - `empty_channel_subscriptions` silently discards
    that content the same way a hard-defaulting test wrapper did in item 4c,
    which is what this exists to avoid.
    """
    from kernel.plugin_base import SubscriptionValue

    subscriptions = {
        (SECURITY_MATRIX_COMPILER, key): SubscriptionValue(from_plugin=SECURITY_MATRIX_COMPILER, key=key, value={})
        for key in CHANNEL_KEYS
    }
    subscriptions[(EFFECTIVE_MODEL_COMPILER, "enforcer_resolution")] = SubscriptionValue(
        from_plugin=EFFECTIVE_MODEL_COMPILER,
        key="enforcer_resolution",
        value=_derive_enforcer_resolution_for(compiled_json),
    )
    subscriptions[(CAPABILITY_FLAGS_COMPILER, "capability_flags")] = SubscriptionValue(
        from_plugin=CAPABILITY_FLAGS_COMPILER,
        key="capability_flags",
        value=_derive_capability_flags_for(compiled_json),
    )
    subscriptions[(WIREGUARD_TUNNELS_COMPILER, "wireguard_tunnels")] = SubscriptionValue(
        from_plugin=WIREGUARD_TUNNELS_COMPILER,
        key="wireguard_tunnels",
        value=_derive_wireguard_tunnels_for(compiled_json),
    )
    subscriptions[(CONTAINERS_COMPILER, "containers")] = SubscriptionValue(
        from_plugin=CONTAINERS_COMPILER, key="containers", value=_derive_containers_for(compiled_json)
    )
    subscriptions[(WIFI_CONFIG_COMPILER, "wifi_config")] = SubscriptionValue(
        from_plugin=WIFI_CONFIG_COMPILER, key="wifi_config", value=_derive_wifi_config_for(compiled_json)
    )
    subscriptions[(ROUTING_POLICIES_COMPILER, "routing_policies")] = SubscriptionValue(
        from_plugin=ROUTING_POLICIES_COMPILER,
        key="routing_policies",
        value=_derive_routing_policies_for(compiled_json),
    )
    subscriptions[(MAC_VLAN_ASSIGNMENTS_COMPILER, "mac_vlan_assignments")] = SubscriptionValue(
        from_plugin=MAC_VLAN_ASSIGNMENTS_COMPILER,
        key="mac_vlan_assignments",
        value=_derive_mac_vlan_assignments_for(compiled_json),
    )
    subscriptions[(BRIDGE_VLANS_COMPILER, "bridge_vlans")] = SubscriptionValue(
        from_plugin=BRIDGE_VLANS_COMPILER, key="bridge_vlans", value=_derive_bridge_vlans_for(compiled_json)
    )
    subscriptions[(VLAN_ENTRIES_COMPILER, "vlans")] = SubscriptionValue(
        from_plugin=VLAN_ENTRIES_COMPILER, key="vlans", value=_derive_vlans_for(compiled_json)
    )
    subscriptions[(BRIDGE_ENTRIES_COMPILER, "bridges")] = SubscriptionValue(
        from_plugin=BRIDGE_ENTRIES_COMPILER, key="bridges", value=_derive_bridges_for(compiled_json)
    )
    subscriptions[(FIREWALL_ENTRIES_COMPILER, "firewall_policies")] = SubscriptionValue(
        from_plugin=FIREWALL_ENTRIES_COMPILER,
        key="firewall_policies",
        value=_derive_firewall_policies_for(compiled_json),
    )
    return subscriptions


__all__ = [
    "BRIDGE_ENTRIES_COMPILER",
    "BRIDGE_VLANS_COMPILER",
    "CAPABILITY_FLAGS_COMPILER",
    "CHANNEL_KEYS",
    "CONTAINERS_COMPILER",
    "EFFECTIVE_MODEL_COMPILER",
    "FIREWALL_ENTRIES_COMPILER",
    "MAC_VLAN_ASSIGNMENTS_COMPILER",
    "ROUTING_POLICIES_COMPILER",
    "SECURITY_MATRIX_COMPILER",
    "VLAN_ENTRIES_COMPILER",
    "WIFI_CONFIG_COMPILER",
    "WIREGUARD_TUNNELS_COMPILER",
    "derived_channel_subscriptions",
    "empty_channel_subscriptions",
    "publish_empty_channels",
]

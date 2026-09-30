#!/usr/bin/env python3
"""MikroTik-owned projection helpers for object generators."""

from __future__ import annotations

from typing import Any

from plugins.generators.projection_core import (  # ADR0078 WP-006: Group canonical name constants
    GROUP_DEVICES,
    GROUP_NETWORK,
    GROUP_SERVICES,
    ProjectionError,
    _group_rows,
    _instance_groups,
    _require_non_empty_str,
    _require_object_ref,
    _sorted_rows,
)

_MIKROTIK_ADAPTER = "cap.firewall.security_matrix.routeros"


def _is_mikrotik_enforcer(instance_id: Any, enforcer_resolution: dict[str, Any]) -> bool:
    """ADR 0118/0119 D-TYPE-1..3: is this instance a resolved RouterOS enforcer?

    Selection by declared capability (enforcer_resolution's adapter), not by
    object_ref name convention (ENFORCER-AXIS-CONFORMANCE.md V-14). Same
    check as the compile-stage compilers' own copy of this helper (this
    module does not import from `plugins/compilers/` - object modules
    duplicate small helpers rather than cross-import, the same pattern
    `_resolved_object_ref` already established across this whole family).
    """
    if not isinstance(instance_id, str) or not instance_id:
        return False
    resolution = enforcer_resolution.get(instance_id) if isinstance(enforcer_resolution, dict) else None
    return isinstance(resolution, dict) and resolution.get("adapter") == _MIKROTIK_ADAPTER


def _extract_security_matrix(
    router_ids: set[str],
    *,
    composed_matrices_by_enforcer: dict[str, dict[str, Any]],
    compiled_vlan_cidrs: dict[str, str],
) -> dict[str, Any]:
    """Read the composed security matrix plan for this projection's router.

    `composed_matrices_by_enforcer` is `base.compiler.security_matrix`'s own
    already-composed, already-validated plan per enforcer (ADR 0118-analysis/
    ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md sections 5c/5d, finding N-07):
    zones and R1-R6 matrix cells, including policy-override (R6) resolution,
    unioned across every scope that enforcer holds under D-COMP-1/D-COMP-2.

    This function used to re-derive all of that itself from raw
    `network_rows` - a third derivation of the same fact, after the
    compiler's own `_calculate_matrix` and the W05 test oracle in
    `test_zone_derivation_parity_w05.py` - and had drifted from it in three
    ways found by reading both side by side (N-07): R6-before-R1 ordering,
    no `enforcement_plane` distinction for same-zone traffic, and a narrower
    untrusted-zone name match. None currently changed rendered output, but
    keeping a second implementation is how W05's divergence happened in the
    first place. Retiring it here removes that risk rather than reproducing
    it once per scope this projection would otherwise need to combine itself.

    `src_vlan_ref`/`dst_vlan_ref` resolution to `src_address`/`dst_address`
    (the F05 fix) is not owned by the compiler and stays here: it is the one
    place that does it, using `compiled_vlan_cidrs` the same way it always
    has.

    Multiple enforcers in `router_ids` are not distinguished: this
    projection's render context carries one `security_matrix` value for the
    whole rendered root, which is the still-blocked V-11/V-12 layout
    question, not this step's scope - fixing rendering to carry one value
    per enforcer needs that Terraform state-layout decision first, not a
    local change here. What changed (ENFORCER-AXIS-CONFORMANCE.md section 4,
    "Two scopes/planes on one device" counterexample, its accepted second
    outcome): more than one enforcer holding a composed plan used to be
    silently resolved by picking the sorted-first router id, matching the
    single-router assumption `default_router_id` already makes elsewhere in
    this module. That silent choice is now an explicit `ProjectionError`
    instead - the real topology has exactly one router with a composed plan,
    so this refusal cannot fire there; it exists for the day a second one is
    added before V-11/V-12 is resolved.

    Returns:
        {
            "instance_id": "inst.security_matrix.mikrotik",  # or several scope
                                                               # ids, comma-joined
            "managed_by_ref": "rtr-mikrotik-example",
            "zones": {...},
            "matrix": {...},
            "policy_overrides": [...],
            "unresolved_vlan_refs": [...],
        }
    """
    enforced_router_ids = sorted(
        router_id
        for router_id in router_ids
        if isinstance(composed_matrices_by_enforcer.get(router_id), dict)
    )
    if len(enforced_router_ids) > 1:
        raise ProjectionError(
            "composed_matrices_by_enforcer holds a composed plan for more than one "
            f"enforcer ({', '.join(enforced_router_ids)}). This projection's render "
            "context carries one security_matrix value for the whole rendered root "
            "(ADR 0118-analysis/ENFORCER-AXIS-CONFORMANCE.md V-11/V-12, blocked on a "
            "reviewed Terraform state-layout change) and cannot silently pick one. "
            "Multi-enforcer rendering needs that layout decision first."
        )

    for router_id in enforced_router_ids:
        composed = composed_matrices_by_enforcer[router_id]

        # F05: resolve src_vlan_ref/dst_vlan_ref to src_address/dst_address.
        # Operates on copies so the published channel is never mutated by a
        # consumer - the same discipline as any other read of shared state.
        policy_overrides: list[dict[str, Any]] = [
            dict(override) for override in (composed.get("policy_overrides") or []) if isinstance(override, dict)
        ]
        unresolved_vlan_refs: list[dict[str, str]] = []
        for override in policy_overrides:
            override_name = str(override.get("name", "unnamed"))
            src_vlan_ref = str(override.get("src_vlan_ref", "")).strip()
            if src_vlan_ref:
                if src_vlan_ref in compiled_vlan_cidrs:
                    override["src_address"] = compiled_vlan_cidrs[src_vlan_ref]
                else:
                    unresolved_vlan_refs.append(
                        {"override": override_name, "field": "src_vlan_ref", "ref": src_vlan_ref}
                    )
            dst_vlan_ref = str(override.get("dst_vlan_ref", "")).strip()
            if dst_vlan_ref:
                if dst_vlan_ref in compiled_vlan_cidrs:
                    override["dst_address"] = compiled_vlan_cidrs[dst_vlan_ref]
                else:
                    unresolved_vlan_refs.append(
                        {"override": override_name, "field": "dst_vlan_ref", "ref": dst_vlan_ref}
                    )

        scope_ids = composed.get("scope_ids")
        instance_id = ", ".join(scope_ids) if isinstance(scope_ids, list) and scope_ids else router_id

        return {
            "instance_id": instance_id,
            "managed_by_ref": router_id,
            "zones": composed.get("zones", {}),
            "matrix": composed.get("matrix", {}),
            "policy_overrides": policy_overrides,
            "unresolved_vlan_refs": unresolved_vlan_refs,
        }

    return {}


def build_mikrotik_projection(
    compiled_json: dict[str, Any],
    *,
    composed_matrices_by_enforcer: dict[str, Any] | None = None,
    vlan_cidr_map: dict[str, str] | None = None,
    capability_flags: dict[str, bool] | None = None,
    wireguard_tunnels: dict[str, Any] | None = None,
    containers: list[dict[str, Any]] | None = None,
    wifi_config: dict[str, Any] | None = None,
    routing_policies: list[dict[str, Any]] | None = None,
    mac_vlan_assignments: list[dict[str, Any]] | None = None,
    bridge_vlans: list[dict[str, Any]] | None = None,
    vlans: list[dict[str, Any]] | None = None,
    bridges: list[dict[str, Any]] | None = None,
    firewall_policies: list[dict[str, Any]] | None = None,
    enforcer_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build stable view for MikroTik Terraform generator.

    `composed_matrices_by_enforcer` and `vlan_cidr_map` are the channels
    `base.compiler.security_matrix` publishes, and they are the only source of
    zone membership, R1-R6 matrix cells and address-domain CIDRs here. Nothing
    in this module derives any of them: that is acceptance case A24, and W07
    puts the derivation in the core rather than in a generate-stage projection.
    `composed_matrices_by_enforcer` replaces the former `security_matrices`
    argument (ADR 0118-analysis/ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md
    sections 5c/5d, N-07): this module used to re-derive R1-R6 itself from raw
    `network_rows`, a third derivation of the same fact; it now reads the
    compiler's already-composed plan for each router directly.

    `capability_flags` is the channel `object.mikrotik.compiler.capability_flags`
    publishes (W07 migration order item 1): conditional-generation booleans
    derived from the same objects/instances this projection already reads.
    This projection no longer derives them itself, for the same reason it does
    not re-derive the matrix or the CIDR map - the fact must exist at compile
    stage, before any validator runs, not only when the generator renders.

    `wireguard_tunnels` is the channel `object.mikrotik.compiler.
    wireguard_tunnels` publishes (W07 migration order item 4a): tunnel,
    interface and peer shape for every WireGuard tunnel this router
    terminates. Derived the same way and for the same reason as the three
    channels above - this projection reads it rather than deriving it.

    `containers` is the channel `object.mikrotik.compiler.containers`
    publishes (W07 migration order item 4b): attachment and publication
    shape for every RouterOS container this router hosts. Derived the same
    way and for the same reason as the channels above.

    `wifi_config` is the channel `object.mikrotik.compiler.wifi_config`
    publishes (W07 migration order item 4c): datapath, configuration,
    security profile and interface-binding shape for every WiFi interface
    this router runs. Derived the same way and for the same reason as the
    channels above.

    `routing_policies` is the channel `object.mikrotik.compiler.
    routing_policies` publishes (W07 migration order item 4d): mangle/NAT/
    firewall rule shape for every policy-based route this router applies,
    with `*_vlan_ref` fields already resolved against the compiler's CIDR
    map. Derived the same way and for the same reason as the channels above.

    `mac_vlan_assignments` is the channel `object.mikrotik.compiler.
    mac_vlan_assignments` publishes (W07 migration order item 4e): bridge
    host entries for devices with a resolved VLAN and secrets reference
    (ADR 0117 L1/L2 separation). Derived the same way and for the same
    reason as the channels above.

    `bridge_vlans` is the channel `object.mikrotik.compiler.bridge_vlans`
    publishes (W07 migration order item 4f): bridge VLAN-filtering entries
    for WiFi interface VLAN membership, derived from `wifi_config` (item
    4c)'s datapath/interface shape. Derived the same way and for the same
    reason as the channels above.

    `vlans` is the channel `object.mikrotik.compiler.vlan_entries` publishes
    (W07 migration order item 4g): VLAN row -> rendered shape (CIDR,
    gateway, DHCP, DNS, MAC-assignment and interface-naming fields) for
    every VLAN a MikroTik router manages. Derived the same way and for the
    same reason as the channels above.

    `bridges` is the channel `object.mikrotik.compiler.bridge_entries`
    publishes (W07 migration order item 4h): bridge row -> rendered shape
    (name, IP, CIDR) for every bridge a MikroTik router manages. Derived
    the same way and for the same reason as the channels above.

    `firewall_policies` is the channel `object.mikrotik.compiler.
    firewall_entries` publishes (W07 migration order item 4i):
    firewall-policy row -> rendered shape (chain, priority, default action,
    rules) for every firewall policy a MikroTik router manages. Derived the
    same way and for the same reason as the channels above. The zone/CIDR
    resolution this projection still applies to the channel's output is not
    part of the derivation itself: it depends on `vlans`, itself already a
    compile-stage channel, the same way policy-based routing's
    `src_vlan_ref` resolution stays local to the routing_policies plugin's
    own scope.

    `None` is an omission and is refused, because the alternative is a projection
    that renders empty address lists and empty tunnel routes while reporting
    success. A caller that means "there are none" passes an empty mapping and
    says so. The production consumer never reaches either case: the generator
    blocks when the compiler published nothing.
    """
    if vlan_cidr_map is None:
        raise ProjectionError(
            "vlan_cidr_map was not supplied; it is published by "
            "'base.compiler.security_matrix' and this projection derives no substitute. "
            "Pass an empty mapping to state that there are no address domains."
        )
    if composed_matrices_by_enforcer is None:
        raise ProjectionError(
            "composed_matrices_by_enforcer was not supplied; it is published by "
            "'base.compiler.security_matrix' and this projection derives no substitute. "
            "Pass an empty mapping to state that there are no matrices."
        )
    if capability_flags is None:
        raise ProjectionError(
            "capability_flags was not supplied; it is published by "
            "'object.mikrotik.compiler.capability_flags' and this projection derives no "
            "substitute. Pass an empty mapping to state that no flags are set."
        )
    if wireguard_tunnels is None:
        raise ProjectionError(
            "wireguard_tunnels was not supplied; it is published by "
            "'object.mikrotik.compiler.wireguard_tunnels' and this projection derives no "
            "substitute. Pass an empty mapping to state that there are no tunnels."
        )
    if containers is None:
        raise ProjectionError(
            "containers was not supplied; it is published by "
            "'object.mikrotik.compiler.containers' and this projection derives no "
            "substitute. Pass an empty list to state that there are no containers."
        )
    if wifi_config is None:
        raise ProjectionError(
            "wifi_config was not supplied; it is published by "
            "'object.mikrotik.compiler.wifi_config' and this projection derives no "
            "substitute. Pass an empty mapping to state that there is no WiFi configuration."
        )
    if routing_policies is None:
        raise ProjectionError(
            "routing_policies was not supplied; it is published by "
            "'object.mikrotik.compiler.routing_policies' and this projection derives no "
            "substitute. Pass an empty list to state that there are no routing policies."
        )
    if mac_vlan_assignments is None:
        raise ProjectionError(
            "mac_vlan_assignments was not supplied; it is published by "
            "'object.mikrotik.compiler.mac_vlan_assignments' and this projection derives no "
            "substitute. Pass an empty list to state that there are no MAC-to-VLAN assignments."
        )
    if bridge_vlans is None:
        raise ProjectionError(
            "bridge_vlans was not supplied; it is published by "
            "'object.mikrotik.compiler.bridge_vlans' and this projection derives no "
            "substitute. Pass an empty list to state that there are no bridge VLAN entries."
        )
    if vlans is None:
        raise ProjectionError(
            "vlans was not supplied; it is published by "
            "'object.mikrotik.compiler.vlan_entries' and this projection derives no "
            "substitute. Pass an empty list to state that there are no VLANs."
        )
    if bridges is None:
        raise ProjectionError(
            "bridges was not supplied; it is published by "
            "'object.mikrotik.compiler.bridge_entries' and this projection derives no "
            "substitute. Pass an empty list to state that there are no bridges."
        )
    if firewall_policies is None:
        raise ProjectionError(
            "firewall_policies was not supplied; it is published by "
            "'object.mikrotik.compiler.firewall_entries' and this projection derives no "
            "substitute. Pass an empty list to state that there are no firewall policies."
        )
    if enforcer_resolution is None:
        raise ProjectionError(
            "enforcer_resolution was not supplied; it is published by "
            "'base.compiler.effective_model' and this projection derives no substitute. "
            "Pass an empty mapping to state that no instance resolved an enforcer type "
            "(ADR 0118-analysis/ENFORCER-AXIS-CONFORMANCE.md V-14)."
        )

    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical=GROUP_DEVICES)
    network = _group_rows(groups, canonical=GROUP_NETWORK)
    service_rows = _group_rows(groups, canonical=GROUP_SERVICES)

    routers: list[dict[str, Any]] = []
    router_ids: set[str] = set()
    for idx, row in enumerate(devices):
        _require_object_ref(row, path=f"compiled_json.instances.devices[{idx}]")
        instance_id = _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
        if _is_mikrotik_enforcer(instance_id, enforcer_resolution):
            export_row = dict(row)
            export_row.pop("instance", None)
            instance_data = export_row.get("instance_data")
            if not isinstance(instance_data, dict):
                instance_data = {}
            routers.append(export_row)
            router_ids.add(instance_id)

    networks: list[dict[str, Any]] = []

    default_router_id = next(iter(sorted(router_ids)), "")

    # VLAN -> CIDR is the compiler's channel, read once and used for routing
    # policy references and for WireGuard `allowed_vlan_refs`. It is not derived
    # here: a second derivation is what A24 forbids, and the absence of a local
    # fallback is what stops a missing channel from rendering as "no CIDRs".
    vlan_cidr_index = vlan_cidr_map

    for idx, row in enumerate(network):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.network[{idx}]")
        _require_object_ref(row, path=f"compiled_json.instances.network[{idx}]")
        export_row = dict(row)
        export_row.pop("instance", None)
        networks.append(export_row)

        # Bridge row -> rendered shape is the channel
        # object.mikrotik.compiler.bridge_entries publishes (W07 migration
        # order item 4h); this projection derives no substitute.

        # VLAN row -> rendered shape is the channel
        # object.mikrotik.compiler.vlan_entries publishes (W07 migration
        # order item 4g); this projection derives no substitute.

    # Policy-based routing shape is the channel
    # object.mikrotik.compiler.routing_policies publishes (W07 migration
    # order item 4d); this projection derives no substitute.

    # Firewall-policy row -> rendered shape is the channel
    # object.mikrotik.compiler.firewall_entries publishes (W07 migration
    # order item 4i); this projection derives no substitute.

    selected_services: list[dict[str, Any]] = []
    for idx, row in enumerate(service_rows):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.services[{idx}]")
        runtime = row.get("runtime")
        if runtime and not isinstance(runtime, dict):
            raise ProjectionError(f"compiled_json.instances.services[{idx}].runtime must be mapping/object")
        target_ref = runtime.get("target_ref") if isinstance(runtime, dict) else None
        if isinstance(target_ref, str) and target_ref in router_ids:
            export_row = dict(row)
            export_row.pop("instance", None)
            selected_services.append(export_row)

    # Build trust-zone to CIDR map from VLANs for firewall zone matching.
    trust_zone_cidrs: dict[str, str] = {}
    for vlan in vlans:
        zone_ref = str(vlan.get("trust_zone_ref") or "").strip()
        cidr = str(vlan.get("cidr") or "").strip()
        if zone_ref and cidr:
            trust_zone_cidrs[zone_ref] = cidr

    # Normalize firewall rules with CIDR resolution.
    normalized_firewall: list[dict[str, Any]] = []
    for policy in firewall_policies:
        rules = policy.get("rules", [])
        normalized_rules: list[dict[str, Any]] = []
        if isinstance(rules, list):
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                src_zone_ref = str(rule.get("src_zone_ref") or "").strip()
                dst_zone_ref = str(rule.get("dst_zone_ref") or "").strip()
                normalized_rules.append(
                    {
                        "action": str(rule.get("action") or policy.get("default_action") or "drop"),
                        "protocol": str(rule.get("protocol") or "any"),
                        "comment": str(rule.get("comment") or policy.get("comment") or ""),
                        "src_zone_ref": src_zone_ref,
                        "dst_zone_ref": dst_zone_ref,
                        "src_cidr": trust_zone_cidrs.get(f"inst.trust_zone.{src_zone_ref}", ""),
                        "dst_cidr": trust_zone_cidrs.get(f"inst.trust_zone.{dst_zone_ref}", ""),
                    }
                )
        normalized = dict(policy)
        normalized["rules"] = normalized_rules
        normalized_firewall.append(normalized)

    # Runtime-derived baseline (single-router case) for NAT/DHCP/addresses.
    runtime_baseline: dict[str, Any] = {
        "nat": [],
        "dns_servers": [],
        "dhcp": {
            "enabled": False,
            "pool_range": "",
            "server_name": "",
            "lease_time": "",
            "network_cidr": "",
            "gateway": "",
            "interface": "",
        },
        "addresses": [],
        "firewall_baseline_rules": [],
    }
    if len(routers) == 1:
        router_data = routers[0].get("instance_data") if isinstance(routers[0].get("instance_data"), dict) else {}
        observed = router_data.get("observed_runtime") if isinstance(router_data, dict) else {}
        if isinstance(observed, dict):
            nat_items = observed.get("nat")
            if isinstance(nat_items, list):
                runtime_baseline["nat"] = [item for item in nat_items if isinstance(item, dict)]
            dns = observed.get("dns")
            if isinstance(dns, dict):
                servers = dns.get("servers")
                if isinstance(servers, list):
                    runtime_baseline["dns_servers"] = [str(v) for v in servers if isinstance(v, str) and v]
            lan = observed.get("lan")
            if isinstance(lan, dict):
                gateway_ref = str(lan.get("gateway_ref") or "").strip()
                dhcp_pool = str(lan.get("dhcp_pool") or "").strip()
                dhcp_server = str(lan.get("dhcp_server") or "").strip()
                dhcp_lease_time = str(lan.get("dhcp_lease_time") or "").strip()
                bridge_if = str(lan.get("bridge_interface") or "bridge").strip() or "bridge"
                lan_cidr = ""
                lan_gateway = ""
                for vlan in vlans:
                    if str(vlan.get("instance_id", "")).strip() == gateway_ref:
                        lan_cidr = str(vlan.get("cidr") or "").strip()
                        lan_gateway = str(vlan.get("gateway") or "").strip()
                        break
                runtime_baseline["dhcp"] = {
                    "enabled": bool(dhcp_pool and lan_cidr and lan_gateway),
                    "pool_range": dhcp_pool,
                    "server_name": dhcp_server or "defconf",
                    "lease_time": dhcp_lease_time or "30m",
                    "network_cidr": lan_cidr,
                    "gateway": lan_gateway,
                    "interface": bridge_if,
                }
            observed_containers = observed.get("containers")
            if isinstance(observed_containers, dict):
                bridge_ip = str(observed_containers.get("bridge_ip") or "").strip()
                bridge_if = str(observed_containers.get("bridge_interface") or "containers").strip() or "containers"
                if bridge_ip:
                    runtime_baseline["addresses"].append({"address": bridge_ip, "interface": bridge_if})
            # Extract firewall baseline rules (critical rules that must exist regardless of zone firewall)
            firewall_cfg = observed.get("firewall")
            if isinstance(firewall_cfg, dict):
                baseline_rules = firewall_cfg.get("baseline_rules")
                if isinstance(baseline_rules, list):
                    for rule in baseline_rules:
                        if isinstance(rule, dict):
                            runtime_baseline["firewall_baseline_rules"].append(rule)

    # WireGuard tunnel/interface/peer shape is the channel
    # object.mikrotik.compiler.wireguard_tunnels publishes (W07 migration
    # order item 4a); this projection derives no substitute.
    wireguard_data = wireguard_tunnels

    # WiFi interface/VLAN membership shape is the channel
    # object.mikrotik.compiler.wifi_config publishes (W07 migration order
    # item 4c); this projection derives no substitute.
    wifi_data = wifi_config

    # Bridge-VLAN membership shape is the channel
    # object.mikrotik.compiler.bridge_vlans publishes (W07 migration order
    # item 4f); this projection derives no substitute.

    security_matrix = _extract_security_matrix(
        router_ids,
        composed_matrices_by_enforcer=composed_matrices_by_enforcer,
        compiled_vlan_cidrs=vlan_cidr_map,
    )

    # MAC-to-VLAN assignment shape is the channel
    # object.mikrotik.compiler.mac_vlan_assignments publishes (W07 migration
    # order item 4e); this projection derives no substitute.

    # Container attachment/publication shape is the channel
    # object.mikrotik.compiler.containers publishes (W07 migration order
    # item 4b); this projection derives no substitute.

    return {
        "routers": _sorted_rows(routers),
        "networks": _sorted_rows(networks),
        "bridges": sorted(bridges, key=lambda b: str(b.get("instance_id", ""))),
        "vlans": sorted(vlans, key=lambda v: (int(v.get("vlan_id") or 0), str(v.get("instance_id", "")))),
        "firewall_policies": sorted(
            normalized_firewall,
            key=lambda p: (int(p.get("priority") or 1000), str(p.get("instance_id", ""))),
        ),
        "routing_policies": sorted(routing_policies, key=lambda p: str(p.get("instance_id", ""))),
        "trust_zone_cidrs": trust_zone_cidrs,
        "runtime_baseline": runtime_baseline,
        "services": _sorted_rows(selected_services),
        "capabilities": capability_flags,
        # WireGuard tunnel data for Terraform generation
        "wireguard": wireguard_data,
        # WiFi configuration data for Terraform generation
        "wifi": wifi_data,
        # Bridge VLAN entries for WiFi interface membership
        "bridge_vlans": bridge_vlans,
        # Security matrix for zone-based firewall (ADR 0110)
        "security_matrix": security_matrix,
        # MAC-based VLAN assignments from device instances
        "mac_vlan_assignments": mac_vlan_assignments,
        # Container configurations for Terraform generation
        "containers": containers,
        "counts": {
            "routers": len(routers),
            "networks": len(networks),
            "bridges": len(bridges),
            "vlans": len(vlans),
            "firewall_policies": len(firewall_policies),
            "routing_policies": len(routing_policies),
            "services": len(selected_services),
            "wireguard_tunnels": len(wireguard_data.get("tunnels", [])),
            "containers": len(containers),
        },
    }

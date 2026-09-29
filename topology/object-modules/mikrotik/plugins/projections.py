#!/usr/bin/env python3
"""MikroTik-owned projection helpers for object generators."""

from __future__ import annotations

from ipaddress import ip_interface
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
    _resolved_object_ref,
    _sorted_rows,
)


def _extract_capabilities(row: dict[str, Any]) -> set[str]:
    """Extract capability IDs from instance row including object capabilities."""
    caps: set[str] = set()

    # Instance-level capabilities
    instance_data = row.get("instance", {}) or {}
    for field_name in ("capabilities", "derived_capabilities", "enabled_capabilities"):
        raw_caps = instance_data.get(field_name)
        if isinstance(raw_caps, list):
            for cap in raw_caps:
                if isinstance(cap, str) and cap:
                    caps.add(cap)

    # Object-level capabilities (from object definition)
    obj_data = row.get("object", {}) or {}
    for field_name in ("enabled_capabilities", "derived_capabilities", "vendor_capabilities"):
        raw_caps = obj_data.get(field_name)
        if isinstance(raw_caps, list):
            for cap in raw_caps:
                if isinstance(cap, str) and cap:
                    caps.add(cap)

    # Root-level capabilities (legacy compatibility)
    for field_name in ("capabilities", "derived_capabilities", "enabled_capabilities"):
        raw_caps = row.get(field_name)
        if isinstance(raw_caps, list):
            for cap in raw_caps:
                if isinstance(cap, str) and cap:
                    caps.add(cap)

    return caps


def _derive_mikrotik_capability_flags(routers: list[dict[str, Any]]) -> dict[str, bool]:
    """Derive boolean capability flags for conditional Terraform generation.

    ADR0078: Capabilities must come from object definitions, not hardcoded model checks.
    """
    all_caps: set[str] = set()
    for router in routers:
        all_caps.update(_extract_capabilities(router))

    return {
        "has_wireguard": any(cap.startswith("cap.net.overlay.vpn.wireguard") for cap in all_caps),
        "has_openvpn": any(cap.startswith("cap.net.overlay.vpn.openvpn") for cap in all_caps),
        "has_ipsec": "cap.net.overlay.vpn.ipsec" in all_caps,
        "has_containers": "cap.net.platform.containers" in all_caps,
        "has_qos_basic": "cap.net.l3.qos.basic" in all_caps,
        "has_qos_advanced": "cap.net.l3.qos.advanced" in all_caps,
        "has_lte": "cap.net.interface.lte" in all_caps,
        "has_wifi": "cap.net.interface.wifi" in all_caps,
        "has_vlan": "cap.net.l2.segmentation.vlan.8021q" in all_caps,
        "has_multi_wan": "cap.net.l3.uplink.multi_uplink" in all_caps,
        "has_failover": "cap.net.l3.uplink.failover" in all_caps,
    }


def _get_object_properties(object_ref: str, objects_map: dict[str, Any]) -> dict[str, Any]:
    """Get properties from compiled object map (effective topology).

    Args:
        object_ref: Object reference (e.g., "obj.network.vlan.servers")
        objects_map: The objects dict from compiled_json["objects"]

    Returns:
        Properties dict from object definition, or empty dict if not found.
    """
    if not object_ref or not isinstance(objects_map, dict):
        return {}

    obj_data = objects_map.get(object_ref)
    if not isinstance(obj_data, dict):
        return {}

    props = obj_data.get("properties")
    if isinstance(props, dict):
        return props
    return {}


def _is_staged_row(row: dict[str, Any]) -> bool:
    status = str(row.get("status", "")).strip().lower()
    notes = str(row.get("notes", "")).strip().lower()
    return status == "modeled" or "currently not configured" in notes


def _build_vlan_entry(row: dict[str, Any], *, managed_by_ref: str, objects_map: dict[str, Any]) -> dict[str, Any]:
    """Extract VLAN configuration from network row."""
    object_ref = _resolved_object_ref(row)
    inst_data = row.get("instance_data", {}) or {}

    # Get properties from compiled object map (effective topology)
    props = _get_object_properties(object_ref, objects_map)

    # Instance data overrides object properties
    vlan_id = inst_data.get("vlan_id") or props.get("vlan_id")
    cidr = inst_data.get("cidr") or props.get("cidr")
    gateway = inst_data.get("gateway") or props.get("gateway")
    mtu = inst_data.get("mtu") or props.get("mtu", 1500)
    dhcp_enabled = inst_data.get("dhcp_enabled") if "dhcp_enabled" in inst_data else props.get("dhcp_enabled", False)
    dns_servers = inst_data.get("dns_servers") or props.get("dns_servers", [])

    is_native_lan = int(vlan_id or 0) == 1
    interface_name = "bridge" if is_native_lan else f"vlan{vlan_id}"

    # Extract MAC assignments for bridge host entries
    mac_assignments = inst_data.get("mac_assignments") or props.get("mac_assignments", [])
    if not isinstance(mac_assignments, list):
        mac_assignments = []

    return {
        "instance_id": row.get("instance_id", ""),
        "name": row.get("instance_id", "").replace("inst.vlan.", "").replace(".", "_"),
        "vlan_id": vlan_id,
        "cidr": cidr,
        "gateway": gateway,
        "mtu": mtu,
        "dhcp_enabled": dhcp_enabled,
        "dhcp_range": inst_data.get("dhcp_range"),
        "dns_servers": dns_servers,
        "managed_by_ref": managed_by_ref,
        "trust_zone_ref": inst_data.get("trust_zone_ref"),
        "staged": _is_staged_row(row),
        "is_native_lan": is_native_lan,
        "interface_name": interface_name,
        "interface_is_resource": not is_native_lan,
        "mac_assignments": mac_assignments,
    }


def _build_bridge_entry(row: dict[str, Any], *, managed_by_ref: str, objects_map: dict[str, Any]) -> dict[str, Any]:
    """Extract bridge configuration from network row."""
    object_ref = _resolved_object_ref(row)
    inst_data = row.get("instance_data", {}) or {}
    props = _get_object_properties(object_ref, objects_map)
    ip_addr = str(inst_data.get("ip") or "").strip()
    cidr = str(inst_data.get("cidr") or "").strip()
    if not cidr and ip_addr:
        try:
            cidr = str(ip_interface(ip_addr).network)
        except ValueError:
            cidr = ""
    name = str(props.get("name") or row.get("instance_id", "").replace("inst.bridge.", "")).strip() or "bridge"
    return {
        "instance_id": row.get("instance_id", ""),
        "name": name.replace(".", "_"),
        "bridge_name": name,
        "ip": ip_addr,
        "cidr": cidr,
        "managed_by_ref": managed_by_ref,
        "staged": _is_staged_row(row),
    }


def _build_firewall_entry(row: dict[str, Any], *, managed_by_ref: str, objects_map: dict[str, Any]) -> dict[str, Any]:
    """Extract firewall policy from network row."""
    object_ref = _resolved_object_ref(row)
    props = _get_object_properties(object_ref, objects_map)
    inst_data = row.get("instance_data", {}) or {}

    return {
        "instance_id": row.get("instance_id", ""),
        "name": row.get("instance_id", "").replace("inst.fw.", "").replace(".", "_"),
        "chain": str(inst_data.get("chain") or "forward"),
        "managed_by_ref": managed_by_ref,
        "priority": int(props.get("priority", 1000)),
        "default_action": str(props.get("default_action", "drop")),
        "rules": props.get("rules", []) if isinstance(props.get("rules"), list) else [],
        "comment": str(row.get("notes", "")),
        "staged": _is_staged_row(row),
    }


def _build_routing_policy_entry(
    row: dict[str, Any],
    *,
    managed_by_ref: str,
    vlan_cidr_index: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Extract policy-based routing configuration from network row.

    Args:
        row: Network instance row from compiled JSON.
        managed_by_ref: Device instance ID managing this policy.
        vlan_cidr_index: VLAN instance_id -> CIDR mapping for resolving refs.

    Supports VLAN reference resolution (ADR-0111 extension):
        - source_match.vlan_ref -> source_subnet (if value not provided)
        - firewall_rules[].src_vlan_ref -> src_address
        - firewall_rules[].dst_vlan_ref -> dst_address
        - mangle_rules[].src_vlan_ref -> src_address
        - mangle_rules[].dst_vlan_ref -> dst_address
        - nat_rules[].src_vlan_ref -> src_address
    """
    if vlan_cidr_index is None:
        vlan_cidr_index = {}

    inst_data = row.get("instance_data", {}) or {}
    mikrotik_config = inst_data.get("mikrotik_config", {}) or {}
    if not isinstance(mikrotik_config, dict):
        mikrotik_config = {}
    source_match = inst_data.get("source_match", {}) or {}
    if not isinstance(source_match, dict):
        source_match = {}
    target_gateway = inst_data.get("target_gateway", {}) or {}
    if not isinstance(target_gateway, dict):
        target_gateway = {}

    instance_id = str(row.get("instance_id", "")).strip()
    name = instance_id.replace("inst.routing_policy.", "").replace(".", "_").replace("-", "_")

    # Resolve source_subnet from vlan_ref if value not provided
    source_subnet = str(source_match.get("value", "")).strip()
    if not source_subnet:
        source_vlan_ref = str(source_match.get("vlan_ref", "")).strip()
        if source_vlan_ref:
            source_subnet = vlan_cidr_index.get(source_vlan_ref, "")

    # Helper to resolve vlan refs in rule dicts
    def resolve_rule_refs(rule: dict[str, Any]) -> dict[str, Any]:
        """Resolve vlan_ref fields to actual CIDRs in a rule dict."""
        resolved = dict(rule)
        # src_vlan_ref -> src_address
        src_ref = str(rule.get("src_vlan_ref", "")).strip()
        if src_ref and not rule.get("src_address"):
            cidr = vlan_cidr_index.get(src_ref)
            if cidr:
                resolved["src_address"] = cidr
        # dst_vlan_ref -> dst_address
        dst_ref = str(rule.get("dst_vlan_ref", "")).strip()
        if dst_ref and not rule.get("dst_address"):
            cidr = vlan_cidr_index.get(dst_ref)
            if cidr:
                resolved["dst_address"] = cidr
        return resolved

    mangle_rules = mikrotik_config.get("mangle_rules", [])
    if not isinstance(mangle_rules, list):
        mangle_rules = []
    routing_table = mikrotik_config.get("routing_table", {})
    if not isinstance(routing_table, dict):
        routing_table = {}
    routes = mikrotik_config.get("routes", [])
    if not isinstance(routes, list):
        routes = []
    nat_rules = mikrotik_config.get("nat_rules", [])
    if not isinstance(nat_rules, list):
        nat_rules = []
    mss_clamp = mikrotik_config.get("mss_clamp", {})
    if not isinstance(mss_clamp, dict):
        mss_clamp = {}
    fasttrack = mikrotik_config.get("fasttrack", {})
    if not isinstance(fasttrack, dict):
        fasttrack = {}
    notrack = mikrotik_config.get("notrack", [])
    if not isinstance(notrack, list):
        notrack = []
    firewall_rules = mikrotik_config.get("firewall_rules", [])
    if not isinstance(firewall_rules, list):
        firewall_rules = []

    # Resolve vlan refs in all rule types
    resolved_mangle = [resolve_rule_refs(r) for r in mangle_rules if isinstance(r, dict)]
    resolved_nat = [resolve_rule_refs(r) for r in nat_rules if isinstance(r, dict)]
    resolved_firewall = [resolve_rule_refs(r) for r in firewall_rules if isinstance(r, dict)]

    return {
        "instance_id": instance_id,
        "name": name,
        "policy_name": str(inst_data.get("policy_name", "")).strip() or name,
        "enabled": bool(inst_data.get("enabled", True)),
        "source_subnet": source_subnet,
        "tunnel_interface": str(target_gateway.get("value", "")).strip(),
        "mangle_rules": resolved_mangle,
        "routing_table": routing_table,
        "routes": [route for route in routes if isinstance(route, dict)],
        "nat_rules": resolved_nat,
        "mss_clamp": mss_clamp if mss_clamp.get("new_mss") else None,
        "fasttrack": fasttrack if fasttrack.get("enabled") else None,
        "notrack": [rule for rule in notrack if isinstance(rule, dict)],
        "firewall_rules": resolved_firewall,
        "managed_by_ref": managed_by_ref,
        "staged": _is_staged_row(row),
    }


def _extract_wifi_config(routers: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract WiFi configuration from router instances.

    Returns:
        {
            "datapaths": [...],      # Unique datapath configurations
            "configurations": [...], # WiFi configurations (SSIDs)
            "securities": [...],     # Security profiles
            "interfaces": [...],     # Interface -> configuration bindings
                                     # (entries with master_interface are
                                     # virtual/slave APs that must be created)
        }
    """
    datapaths: dict[str, dict[str, Any]] = {}  # keyed by name to dedupe
    configurations: list[dict[str, Any]] = []
    securities: dict[str, dict[str, Any]] = {}  # keyed by name to dedupe
    interfaces: list[dict[str, Any]] = []

    for router in routers:
        instance_data = router.get("instance_data", {})
        if not isinstance(instance_data, dict):
            continue

        observed = instance_data.get("observed_runtime", {})
        if not isinstance(observed, dict):
            continue

        wifi_config = observed.get("wifi", {})
        if not isinstance(wifi_config, dict):
            continue

        for iface_name, iface_data in wifi_config.items():
            if not isinstance(iface_data, dict):
                continue

            ssid = iface_data.get("ssid")
            if not ssid:
                continue

            # Extract datapath
            datapath = iface_data.get("datapath")
            if isinstance(datapath, dict):
                dp_name = datapath.get("name", "")
                if dp_name and dp_name not in datapaths:
                    dp_entry: dict[str, Any] = {
                        "name": dp_name,
                        "bridge": datapath.get("bridge", "bridge"),
                        "comment": f"{ssid} datapath - managed by topology",
                    }
                    # Only include vlan_id if present and non-zero
                    vlan_id = datapath.get("vlan_id")
                    if vlan_id:
                        dp_entry["vlan_id"] = int(vlan_id)
                    datapaths[dp_name] = dp_entry

            # Extract security profile
            # Supports both string format ("wpa2-psk") and object format:
            # security:
            #   authentication_types: [wpa2-psk, wpa3-psk]
            #   fast_transition: true
            #   fast_transition_over_ds: true
            security = iface_data.get("security")
            sec_name = None
            if security:
                sec_name = f"sec-{iface_name}"
                if sec_name not in securities:
                    sec_entry: dict[str, Any] = {
                        "name": sec_name,
                        "passphrase": True,  # indicates variable needed
                        "comment": f"{ssid} security - managed by topology",
                    }
                    if isinstance(security, str):
                        # Simple string format: "wpa2-psk"
                        sec_entry["authentication_types"] = [security]
                    elif isinstance(security, dict):
                        # Object format with WPA3/FT support
                        auth_types = security.get("authentication_types", [])
                        if isinstance(auth_types, list):
                            sec_entry["authentication_types"] = auth_types
                        elif isinstance(auth_types, str):
                            sec_entry["authentication_types"] = [auth_types]
                        # Fast Transition (802.11r) support
                        if security.get("fast_transition"):
                            sec_entry["ft"] = True
                        if security.get("fast_transition_over_ds"):
                            sec_entry["ft_over_ds"] = True
                    securities[sec_name] = sec_entry

            # Build configuration entry
            cfg_name = f"cfg-{iface_name}"
            cfg_entry: dict[str, Any] = {
                "name": cfg_name,
                "ssid": ssid,
                "mode": iface_data.get("mode", "ap"),
                "comment": f"{ssid} - managed by topology",
            }
            if sec_name:
                cfg_entry["security"] = sec_name
            if isinstance(datapath, dict) and datapath.get("name"):
                cfg_entry["datapath"] = datapath.get("name")

            configurations.append(cfg_entry)

            # Interface -> configuration binding. Staged SSIDs are not bound
            # (their configuration exists but no AP broadcasts it yet).
            # Entries with master_interface describe virtual (slave) APs
            # (e.g. VPN-Germany on wifi1) which do NOT exist out of the box
            # on a fresh RouterOS and must be created by the deploy tooling.
            status = str(iface_data.get("status", "")).strip().lower()
            if status != "staged":
                iface_entry: dict[str, Any] = {
                    # Physical slots use the mapping key (wifi1/wifi2);
                    # virtual APs carry an explicit interface name.
                    "name": str(iface_data.get("name") or iface_name),
                    "configuration": cfg_name,
                }
                master = str(iface_data.get("master_interface") or "").strip()
                if master:
                    iface_entry["master_interface"] = master

                # Channel configuration (frequency in MHz, band, width)
                frequency = iface_data.get("frequency")
                if frequency:
                    iface_entry["frequency"] = int(frequency)
                band = iface_data.get("band")
                if band:
                    iface_entry["band"] = str(band)
                channel_width = iface_data.get("channel_width")
                if channel_width:
                    iface_entry["channel_width"] = str(channel_width)

                interfaces.append(iface_entry)

    return {
        "datapaths": list(datapaths.values()),
        "configurations": configurations,
        "securities": list(securities.values()),
        "interfaces": interfaces,
    }


def _extract_bridge_vlans(
    routers: list[dict[str, Any]],
    wifi_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract bridge VLAN entries for WiFi interface VLAN membership.

    When bridge_vlan_filtering is enabled, WiFi interfaces must be explicitly
    added to bridge VLANs. Interfaces with datapaths that have no vlan_id go
    to VLAN 1 (untagged), interfaces with vlan_id go to that VLAN (tagged on bridge).

    Returns:
        List of bridge VLAN entries:
        [
            {"bridge": "bridge", "vlan_id": 1, "untagged": ["bridge", "wifi1", "wifi2"], "tagged": []},
            {"bridge": "bridge", "vlan_id": 55, "untagged": [], "tagged": ["bridge"]},
        ]
    """
    bridge_vlans: dict[int, dict[str, Any]] = {}  # vlan_id -> entry

    for router in routers:
        instance_data = router.get("instance_data", {})
        if not isinstance(instance_data, dict):
            continue

        observed = instance_data.get("observed_runtime", {})
        if not isinstance(observed, dict):
            continue

        lan = observed.get("lan", {})
        if not isinstance(lan, dict):
            continue

        # Check if VLAN filtering is enabled
        vlan_filtering = lan.get("bridge_vlan_filtering", False)
        if not vlan_filtering:
            continue

        bridge_name = str(lan.get("bridge_interface", "bridge")).strip() or "bridge"
        bridge_ports = lan.get("bridge_ports", [])
        if not isinstance(bridge_ports, list):
            bridge_ports = []

        # Build datapath -> vlan_id mapping from wifi_data
        datapath_vlan: dict[str, int] = {}  # datapath name -> vlan_id (0 means native/VLAN 1)
        for dp in wifi_data.get("datapaths", []):
            dp_name = str(dp.get("name", "")).strip()
            vlan_id = dp.get("vlan_id", 0)
            if dp_name:
                datapath_vlan[dp_name] = int(vlan_id) if vlan_id else 0

        # Build interface -> datapath mapping from wifi_data
        iface_datapath: dict[str, str] = {}  # interface name -> datapath name
        for cfg in wifi_data.get("configurations", []):
            cfg_name = str(cfg.get("name", "")).strip()
            dp_name = str(cfg.get("datapath", "")).strip()
            if cfg_name and dp_name:
                # Find interface using this configuration
                for iface in wifi_data.get("interfaces", []):
                    if str(iface.get("configuration", "")).strip() == cfg_name:
                        iface_name = str(iface.get("name", "")).strip()
                        if iface_name:
                            iface_datapath[iface_name] = dp_name

        # Initialize VLAN 1 with bridge itself as untagged
        if 1 not in bridge_vlans:
            bridge_vlans[1] = {
                "bridge": bridge_name,
                "vlan_id": 1,
                "untagged": [bridge_name],
                "tagged": [],
            }

        # Process each bridge port
        for port in bridge_ports:
            port_name = str(port).strip()
            if not port_name:
                continue

            # Check if this is a WiFi interface with a datapath
            dp_name = iface_datapath.get(port_name, "")
            vlan_id = datapath_vlan.get(dp_name, 0) if dp_name else 0

            if vlan_id == 0:
                # Native VLAN 1 - add as untagged
                if port_name not in bridge_vlans[1]["untagged"]:
                    bridge_vlans[1]["untagged"].append(port_name)
            else:
                # Tagged VLAN - create entry if needed
                if vlan_id not in bridge_vlans:
                    bridge_vlans[vlan_id] = {
                        "bridge": bridge_name,
                        "vlan_id": vlan_id,
                        "untagged": [],
                        "tagged": [bridge_name],  # Bridge itself is tagged for VLAN trunking
                    }
                # Add WiFi interface as untagged (it sends/receives untagged frames for this VLAN)
                if port_name not in bridge_vlans[vlan_id]["untagged"]:
                    bridge_vlans[vlan_id]["untagged"].append(port_name)

    return sorted(bridge_vlans.values(), key=lambda x: x.get("vlan_id", 0))


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
    question, not this step's scope. The sorted-first router id with a
    composed plan is selected - deterministic, and matching the
    single-router assumption `default_router_id` already makes elsewhere in
    this module - rather than depending on row order the way the retired
    derivation implicitly did.

    Returns:
        {
            "instance_id": "inst.security_matrix.mikrotik",  # or several scope
                                                               # ids, comma-joined
            "managed_by_ref": "rtr-mikrotik-chateau",
            "zones": {...},
            "matrix": {...},
            "policy_overrides": [...],
            "unresolved_vlan_refs": [...],
        }
    """
    for router_id in sorted(router_ids):
        composed = composed_matrices_by_enforcer.get(router_id)
        if not isinstance(composed, dict):
            continue

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


def _extract_wireguard_tunnels(
    network_rows: list[dict[str, Any]],
    router_ids: set[str],
    vlan_cidr_index: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Extract WireGuard tunnels where MikroTik router is an endpoint.

    Args:
        network_rows: Network instance rows from compiled JSON.
        router_ids: Set of MikroTik router instance IDs.
        vlan_cidr_index: VLAN instance_id -> CIDR index for resolving allowed_vlan_refs (ADR-0111).

    Returns:
        {
            "tunnels": [...],  # List of tunnel configs for this router
            "interfaces": [...],  # List of WireGuard interfaces with their peers
            "wireguard_address": "192.0.2.1/30",  # Primary interface address (legacy)
            "wireguard_listen_port": 51820,  # Primary listen port (legacy)
            "wireguard_mtu": 1420,
            "wireguard_peers": [...],  # Primary interface peers (legacy)
        }
    """
    if vlan_cidr_index is None:
        vlan_cidr_index = {}
    tunnels: list[dict[str, Any]] = []

    # Group by interface name for multi-interface support
    interfaces_by_name: dict[str, dict[str, Any]] = {}

    for row in network_rows:
        object_ref = _resolved_object_ref(row)
        if "wireguard_tunnel" not in object_ref:
            continue

        inst_data = row.get("instance_data", {})
        if not isinstance(inst_data, dict):
            continue

        # Check if MikroTik router is endpoint_a (typically client/initiator)
        endpoint_a = inst_data.get("endpoint_a", {})
        endpoint_b = inst_data.get("endpoint_b", {})

        local_endpoint = None
        remote_endpoint = None

        # Find which endpoint is our MikroTik router
        if isinstance(endpoint_a, dict):
            device_ref = str(endpoint_a.get("device_ref", "")).strip()
            if device_ref in router_ids:
                local_endpoint = endpoint_a
                remote_endpoint = endpoint_b

        if not local_endpoint and isinstance(endpoint_b, dict):
            device_ref = str(endpoint_b.get("device_ref", "")).strip()
            if device_ref in router_ids:
                local_endpoint = endpoint_b
                remote_endpoint = endpoint_a

        if not local_endpoint or not isinstance(remote_endpoint, dict):
            continue

        tunnel_name = inst_data.get("tunnel_name", "wg0")

        # Extract local interface config
        local_ip = str(local_endpoint.get("tunnel_ip", "")).strip()
        tunnel_network = str(inst_data.get("tunnel_network", "")).strip()
        interface_address = ""
        if local_ip:
            # Check if IP already includes prefix
            if "/" in local_ip:
                interface_address = local_ip
            elif tunnel_network:
                # Combine IP with network prefix from tunnel_network
                try:
                    prefix = tunnel_network.split("/")[1] if "/" in tunnel_network else "30"
                    interface_address = f"{local_ip}/{prefix}"
                except (IndexError, ValueError):
                    interface_address = f"{local_ip}/30"
            else:
                interface_address = f"{local_ip}/30"

        local_role = str(local_endpoint.get("role", "")).strip()
        # Use explicit listen_port if set, otherwise 0 for client mode
        # (ADR-0112: clients can have listen_port for legacy peer support)
        listen_port = int(local_endpoint.get("listen_port", 0) or 0)
        mtu = int(inst_data.get("mtu", 1420) or 1420)

        # Build peer config for remote endpoint
        remote_name = str(remote_endpoint.get("device_ref", "unknown")).strip()
        remote_role = str(remote_endpoint.get("role", "")).strip()

        # Allowed IPs from the remote endpoint's configuration
        # This is what the remote peer is allowed to send through the tunnel
        remote_allowed_ips = remote_endpoint.get("allowed_ips", [])
        allowed_ips: list[str] = []
        if isinstance(remote_allowed_ips, list):
            for ip in remote_allowed_ips:
                if isinstance(ip, str) and ip:
                    allowed_ips.append(ip)

        # ADR-0111: resolve allowed_vlan_refs against the compiler's map. The map
        # spans every address domain, not only the MikroTik-managed ones, because
        # a tunnel may allow a VLAN another device owns.
        remote_vlan_refs = remote_endpoint.get("allowed_vlan_refs", [])
        if isinstance(remote_vlan_refs, list):
            allowed_ips.extend(
                vlan_cidr_index[ref.strip()]
                for ref in remote_vlan_refs
                if isinstance(ref, str) and ref.strip() in vlan_cidr_index
            )

        # If allowed_ips is empty, at least add remote tunnel IP
        if not allowed_ips:
            remote_ip = str(remote_endpoint.get("tunnel_ip", "")).strip()
            if remote_ip:
                # Strip prefix if present and add /32
                base_ip = remote_ip.split("/")[0] if "/" in remote_ip else remote_ip
                allowed_ips.append(f"{base_ip}/32")

        peer_config: dict[str, Any] = {
            "name": remote_name,
            "allowed_ips": allowed_ips,
            "comment": f"Remote: {remote_name}",
        }

        # Server endpoint info (for client-initiated connections)
        if remote_role == "server":
            public_endpoint = remote_endpoint.get("public_endpoint", "")
            if public_endpoint:
                peer_config["endpoint_address"] = public_endpoint
                peer_config["endpoint_port"] = int(remote_endpoint.get("listen_port", 51820) or 51820)
            # Client needs keepalive
            local_keepalive = local_endpoint.get("persistent_keepalive")
            keepalive = local_keepalive if local_keepalive else inst_data.get("keepalive_interval", 25)
            if keepalive:
                peer_config["persistent_keepalive"] = f"{keepalive}s"

        # Mark that secrets are needed (not stored in projection)
        peer_config["preshared_key"] = True  # Indicates preshared key is used

        # Determine interface list for MikroTik firewall
        # Priority: local_endpoint.mikrotik_interface_list > firewall.mikrotik_interface_list > "LAN"
        interface_list = local_endpoint.get("mikrotik_interface_list")
        if not interface_list:
            firewall_cfg = inst_data.get("firewall", {})
            if isinstance(firewall_cfg, dict):
                interface_list = firewall_cfg.get("mikrotik_interface_list")
        if not interface_list:
            interface_list = "LAN"

        # Initialize interface if not seen yet
        if tunnel_name not in interfaces_by_name:
            interfaces_by_name[tunnel_name] = {
                "name": tunnel_name,
                "address": interface_address,
                "listen_port": listen_port if listen_port > 0 else None,
                "mtu": mtu,
                "interface_list": interface_list,
                "peers": [],
            }
        else:
            # Update address if not set
            if not interfaces_by_name[tunnel_name]["address"] and interface_address:
                interfaces_by_name[tunnel_name]["address"] = interface_address
            # Update listen_port if we found a server endpoint
            if listen_port > 0 and not interfaces_by_name[tunnel_name]["listen_port"]:
                interfaces_by_name[tunnel_name]["listen_port"] = listen_port

        interfaces_by_name[tunnel_name]["peers"].append(peer_config)

        tunnels.append(
            {
                "instance_id": row.get("instance_id", ""),
                "tunnel_name": tunnel_name,
                "local_endpoint": local_endpoint,
                "remote_endpoint": remote_endpoint,
            }
        )

    # Build interfaces list sorted by name
    interfaces = sorted(interfaces_by_name.values(), key=lambda x: x["name"])

    # Legacy compatibility: extract primary (wg0) interface data
    primary_interface = interfaces_by_name.get("wg0", {})
    legacy_address = primary_interface.get("address", "")
    legacy_listen_port = primary_interface.get("listen_port", 51820) or 51820
    legacy_mtu = primary_interface.get("mtu", 1420)
    legacy_peers = primary_interface.get("peers", [])

    return {
        "tunnels": tunnels,
        "interfaces": interfaces,
        "wireguard_address": legacy_address,
        "wireguard_listen_port": legacy_listen_port,
        "wireguard_mtu": legacy_mtu,
        "wireguard_peers": legacy_peers,
    }


def _extract_containers(
    container_rows: list[dict[str, Any]],
    router_ids: set[str],
) -> list[dict[str, Any]]:
    """Extract container configurations from routeros_container instances.

    Extracts container definitions for MikroTik routers, including:
    - Container name, image, root_dir, start_on_boot, logging
    - Veth network configuration (name, address, gateway)
    - Environment variables with _REF suffix resolution for secrets

    Note: All containers in the routeros_container group are inherently
    for RouterOS devices, so host_ref filtering is optional. When router_ids
    is provided and non-empty, containers are filtered to match.

    Args:
        container_rows: Container instance rows from routeros_container group.
        router_ids: Set of MikroTik router instance IDs (for filtering if provided).

    Returns:
        List of container definitions:
        [
            {
                "instance_id": "docker-amneziawg-russia",
                "name": "awg-proxy-russia",
                "tf_name": "awg_proxy_russia",
                "image": "ghcr.io/timbrs/awg-proxy:latest",
                "root_dir": "/usb1/containers/awg-proxy-russia",
                "start_on_boot": True,
                "logging": True,
                "comment": "AWG-Proxy container...",
                "veth_name": "veth-awg-ru",
                "veth_address": "198.51.100.2/30",
                "veth_gateway": "198.51.100.1",
                "envs": [
                    {"key": "AWG_LISTEN", "value": ":51820", "is_secret": False},
                    {"key": "AWG_REMOTE", "var_name": "awg_proxy_russia_awg_remote", "is_secret": True},
                    ...
                ],
                "managed_by_ref": "rtr-example",
            }
        ]
    """
    containers: list[dict[str, Any]] = []

    # Determine default managed_by (first router if single-router topology)
    default_router = next(iter(sorted(router_ids)), "") if router_ids else ""

    for row in container_rows:
        instance_id = str(row.get("instance_id", "")).strip()
        if not instance_id:
            continue

        inst_data = row.get("instance_data", {})
        if not isinstance(inst_data, dict):
            inst_data = {}

        # Try to get host_ref from various locations
        host_ref = str(inst_data.get("host_ref", "")).strip()
        if not host_ref:
            host_ref = str(row.get("host_ref", "")).strip()

        # In single-router topologies, assign all containers to that router
        # The routeros_container group is inherently for RouterOS devices
        if not host_ref and len(router_ids) == 1:
            host_ref = default_router

        # Extract runtime configuration (may be at root level or in instance_data)
        runtime = inst_data.get("runtime")
        if not isinstance(runtime, dict) or not runtime:
            runtime = row.get("runtime")
        if not isinstance(runtime, dict):
            runtime = {}

        container_name = str(runtime.get("name", "")).strip()
        if not container_name:
            # Fallback to instance_id without prefix
            container_name = instance_id.replace("docker-", "").replace("inst.", "")

        # Build Terraform-safe name (replace hyphens with underscores)
        tf_name = container_name.replace("-", "_")

        # Extract network configuration (may be at root level or in instance_data)
        network = inst_data.get("network")
        if not isinstance(network, dict) or not network:
            network = row.get("network")
        if not isinstance(network, dict):
            network = {}

        veth_name = str(network.get("veth_name", "")).strip()
        veth_address = str(network.get("address", "")).strip()
        veth_gateway = str(network.get("gateway", "")).strip()

        # Extract environment variables, handling _REF suffix for secrets
        env_dict = runtime.get("env", {})
        if not isinstance(env_dict, dict):
            env_dict = {}

        envs: list[dict[str, Any]] = []
        for key, value in sorted(env_dict.items()):
            if key.endswith("_REF"):
                # Secret reference: strip _REF suffix, generate Terraform variable name
                actual_key = key[:-4]  # Remove "_REF" suffix
                var_name = f"{tf_name}_{actual_key.lower()}"
                envs.append(
                    {
                        "key": actual_key,
                        "var_name": var_name,
                        "secrets_ref": str(value),
                        "is_secret": True,
                    }
                )
            else:
                # Literal value
                envs.append(
                    {
                        "key": key,
                        "value": str(value),
                        "is_secret": False,
                    }
                )

        # Extract notes for comment
        notes = str(row.get("notes", "")).strip()
        comment = notes.split("\n")[0] if notes else f"Container {container_name}"

        # Extract wireguard_interface configuration (for AWG proxy containers)
        wg_interface_raw = inst_data.get("wireguard_interface")
        if not isinstance(wg_interface_raw, dict) or not wg_interface_raw:
            wg_interface_raw = row.get("wireguard_interface")

        wireguard_interface = None
        if isinstance(wg_interface_raw, dict) and wg_interface_raw.get("name"):
            wg_name = str(wg_interface_raw.get("name", "")).strip()
            wg_tf_name = wg_name.replace("-", "_")

            # Extract peer configuration
            peer_raw = wg_interface_raw.get("peer", {})
            peer_config = None
            if isinstance(peer_raw, dict):
                # Endpoint is container's veth address (strip /prefix)
                endpoint_addr = veth_address.split("/")[0] if "/" in veth_address else veth_address
                # Parse endpoint port from peer.endpoint or default to 51820
                peer_endpoint = str(peer_raw.get("endpoint", "")).strip()
                if ":" in peer_endpoint:
                    endpoint_port = int(peer_endpoint.split(":")[-1])
                else:
                    endpoint_port = 51820

                peer_config = {
                    "public_key_var": f"{tf_name}_wg_peer_public_key",
                    "public_key_ref": str(peer_raw.get("public_key_ref", "")).strip(),
                    "preshared_key_var": f"{tf_name}_wg_peer_preshared_key",
                    "preshared_key_ref": str(peer_raw.get("preshared_key_ref", "")).strip() or None,
                    "endpoint_address": endpoint_addr,
                    "endpoint_port": endpoint_port,
                    "allowed_ips": peer_raw.get("allowed_ips", ["0.0.0.0/0"]),
                    "persistent_keepalive": peer_raw.get("persistent_keepalive", 25),
                }

            wireguard_interface = {
                "name": wg_name,
                "tf_name": wg_tf_name,
                "listen_port": int(wg_interface_raw.get("listen_port", 51820) or 51820),
                "private_key_var": f"{tf_name}_wg_private_key",
                "private_key_ref": str(wg_interface_raw.get("private_key_ref", "")).strip(),
                "address": str(wg_interface_raw.get("address", "")).strip(),
                "mtu": int(wg_interface_raw.get("mtu", 1420) or 1420),
                "interface_list": str(wg_interface_raw.get("interface_list", "VPN_EXIT")).strip() or "VPN_EXIT",
                "peer": peer_config,
            }

        containers.append(
            {
                "instance_id": instance_id,
                "name": container_name,
                "tf_name": tf_name,
                "image": str(runtime.get("image", "")).strip(),
                "root_dir": str(runtime.get("root_dir", "")).strip(),
                "start_on_boot": bool(runtime.get("start_on_boot", True)),
                "logging": bool(runtime.get("logging", True)),
                "comment": comment,
                "veth_name": veth_name,
                "veth_address": veth_address,
                "veth_gateway": veth_gateway,
                "envs": envs,
                "wireguard_interface": wireguard_interface,
                "managed_by_ref": host_ref,
            }
        )

    return sorted(containers, key=lambda c: c.get("name", ""))


def _extract_mac_vlan_assignments(
    all_groups: dict[str, list[dict[str, Any]]],
    vlan_id_index: dict[str, int],
) -> list[dict[str, Any]]:
    """Extract MAC-based VLAN assignments from device instances.

    Finds devices with both vlan_ref and secrets_ref, then builds
    assignment entries for bridge host generation.

    Supports ADR 0117 L1/L2 separation:
    - Direct: device has vlan_ref and secrets_ref
    - Indirect: device has provides_ref -> L2 iot_interface has vlan_ref/secrets_ref

    Args:
        all_groups: All instance groups from compiled JSON.
        vlan_id_index: Mapping of vlan instance_id to vlan_id.

    Returns:
        List of assignment entries:
        [
            {
                "device_id": "inst.device.tv-sony-bravia",
                "device_name": "Sony Bravia AJ9",
                "secrets_ref": "secrets.instances.tv-sony-bravia",
                "secrets_path": "instances/tv-sony-bravia.yaml",
                "vlan_ref": "inst.vlan.vpn_germany",
                "vlan_id": 55,
                "comment": "Sony Bravia AJ9 -> VLAN 55",
            }
        ]
    """
    assignments: list[dict[str, Any]] = []

    # Build L2 interface index: interface_id -> {vlan_ref, secrets_ref, device_ref}
    # ADR 0117: IoT interfaces are in network group with iot_interface in instance_id
    l2_interface_index: dict[str, dict[str, str]] = {}
    network_rows = all_groups.get("network", [])
    for net_row in network_rows:
        net_instance_id = str(net_row.get("instance_id", "")).strip()
        if "iot_interface" not in net_instance_id:
            continue
        net_inst_data = net_row.get("instance_data", {})
        if not isinstance(net_inst_data, dict):
            continue
        l2_interface_index[net_instance_id] = {
            "vlan_ref": str(net_inst_data.get("vlan_ref", "")).strip(),
            "secrets_ref": str(net_inst_data.get("secrets_ref", "")).strip(),
            "device_ref": str(net_inst_data.get("device_ref", "")).strip(),
        }

    # Check devices group for device instances with vlan_ref
    devices = all_groups.get("devices", [])

    for row in devices:
        instance_id = str(row.get("instance_id", "")).strip()
        if not instance_id.startswith("inst.device."):
            continue

        inst_data = row.get("instance_data", {})
        if not isinstance(inst_data, dict):
            continue

        # Try direct vlan_ref/secrets_ref on device first
        vlan_ref = str(inst_data.get("vlan_ref", "")).strip()
        secrets_ref = str(inst_data.get("secrets_ref", "")).strip()

        # ADR 0117: If not found, check provides_ref for L2 interface
        if not vlan_ref or not secrets_ref:
            provides_ref = str(inst_data.get("provides_ref", "")).strip()
            if provides_ref and provides_ref in l2_interface_index:
                l2_data = l2_interface_index[provides_ref]
                if not vlan_ref:
                    vlan_ref = l2_data.get("vlan_ref", "")
                if not secrets_ref:
                    secrets_ref = l2_data.get("secrets_ref", "")

        if not vlan_ref or not secrets_ref:
            continue

        vlan_id = vlan_id_index.get(vlan_ref)
        if not vlan_id:
            continue

        # Convert secrets_ref to path: secrets.instances.foo -> instances/foo.yaml
        secrets_path = ""
        if secrets_ref.startswith("secrets."):
            secrets_path = secrets_ref[8:].replace(".", "/") + ".yaml"

        device_name = str(inst_data.get("device_name", "")).strip()
        if not device_name:
            device_name = instance_id.replace("inst.device.", "")

        assignments.append(
            {
                "device_id": instance_id,
                "device_name": device_name,
                "secrets_ref": secrets_ref,
                "secrets_path": secrets_path,
                "vlan_ref": vlan_ref,
                "vlan_id": vlan_id,
                "comment": f"{device_name} -> VLAN {vlan_id}",
            }
        )

    return sorted(assignments, key=lambda x: (x.get("vlan_id", 0), x.get("device_id", "")))


def build_mikrotik_projection(
    compiled_json: dict[str, Any],
    *,
    composed_matrices_by_enforcer: dict[str, Any] | None = None,
    vlan_cidr_map: dict[str, str] | None = None,
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
    # Extract objects map for property lookups (ADR contract: use compiled topology only)
    objects_map = compiled_json.get("objects", {})
    if not isinstance(objects_map, dict):
        objects_map = {}

    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical=GROUP_DEVICES)
    network = _group_rows(groups, canonical=GROUP_NETWORK)
    service_rows = _group_rows(groups, canonical=GROUP_SERVICES)
    firewall_rows = groups.get("firewall", [])
    container_rows = groups.get("routeros_container", [])

    routers: list[dict[str, Any]] = []
    router_ids: set[str] = set()
    for idx, row in enumerate(devices):
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.devices[{idx}]")
        instance_id = _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
        if object_ref.startswith("obj.mikrotik."):
            export_row = dict(row)
            export_row.pop("instance", None)
            instance_data = export_row.get("instance_data")
            if not isinstance(instance_data, dict):
                instance_data = {}
            routers.append(export_row)
            router_ids.add(instance_id)

    networks: list[dict[str, Any]] = []
    bridges: list[dict[str, Any]] = []
    vlans: list[dict[str, Any]] = []
    firewall_policies: list[dict[str, Any]] = []
    routing_policies: list[dict[str, Any]] = []

    default_router_id = next(iter(sorted(router_ids)), "")

    # VLAN -> CIDR is the compiler's channel, read once and used for routing
    # policy references and for WireGuard `allowed_vlan_refs`. It is not derived
    # here: a second derivation is what A24 forbids, and the absence of a local
    # fallback is what stops a missing channel from rendering as "no CIDRs".
    vlan_cidr_index = vlan_cidr_map

    for idx, row in enumerate(network):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.network[{idx}]")
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.network[{idx}]")
        export_row = dict(row)
        export_row.pop("instance", None)
        networks.append(export_row)
        inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
        managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()

        if "bridge" in object_ref:
            host_ref = str(inst_data.get("host_ref") or "").strip()
            if not managed_by_ref and host_ref in router_ids:
                managed_by_ref = host_ref
            if managed_by_ref in router_ids:
                bridges.append(_build_bridge_entry(row, managed_by_ref=managed_by_ref, objects_map=objects_map))

        # Extract VLANs managed by MikroTik routers.
        # Note: routing_policy objects (e.g. obj.network.routing_policy.vpn_vlan)
        # also contain "vlan" in their ref and must not be treated as VLANs.
        if "vlan" in object_ref and "routing_policy" not in object_ref:
            if not managed_by_ref and len(router_ids) == 1:
                # VLAN instances are treated as router-owned in single-router topology.
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
                vlan_entry = _build_vlan_entry(row, managed_by_ref=managed_by_ref, objects_map=objects_map)
                vlans.append(vlan_entry)

        # Extract policy-based routing (e.g. VPN VLAN via WireGuard) managed by MikroTik routers.
        if "routing_policy" in object_ref:
            if not managed_by_ref and len(router_ids) == 1:
                managed_by_ref = default_router_id
            if managed_by_ref in router_ids:
                routing_policies.append(
                    _build_routing_policy_entry(row, managed_by_ref=managed_by_ref, vlan_cidr_index=vlan_cidr_index)
                )

    # Extract firewall policies from dedicated firewall group.
    for idx, row in enumerate(firewall_rows):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.firewall[{idx}]")
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.firewall[{idx}]")
        if "firewall_policy" not in object_ref:
            continue
        inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
        managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
        if not managed_by_ref and len(router_ids) == 1:
            managed_by_ref = default_router_id
        if managed_by_ref in router_ids:
            firewall_policies.append(_build_firewall_entry(row, managed_by_ref=managed_by_ref, objects_map=objects_map))

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
            containers = observed.get("containers")
            if isinstance(containers, dict):
                bridge_ip = str(containers.get("bridge_ip") or "").strip()
                bridge_if = str(containers.get("bridge_interface") or "containers").strip() or "containers"
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

    # Extract WireGuard tunnel configurations for MikroTik routers
    # Note: vlan_cidr_index was built earlier for routing policy resolution
    wireguard_data = _extract_wireguard_tunnels(network, router_ids, vlan_cidr_index)

    # Extract WiFi configurations from router instances
    wifi_data = _extract_wifi_config(routers)

    # Extract bridge VLAN entries for WiFi interface membership
    bridge_vlans = _extract_bridge_vlans(routers, wifi_data)

    security_matrix = _extract_security_matrix(
        router_ids,
        composed_matrices_by_enforcer=composed_matrices_by_enforcer,
        compiled_vlan_cidrs=vlan_cidr_map,
    )

    # Build VLAN ID index for MAC-based assignments
    vlan_id_index: dict[str, int] = {}
    for vlan in vlans:
        inst_id = str(vlan.get("instance_id", "")).strip()
        vid = vlan.get("vlan_id")
        if inst_id and vid:
            vlan_id_index[inst_id] = int(vid)

    # Extract MAC-based VLAN assignments from device instances
    mac_vlan_assignments = _extract_mac_vlan_assignments(groups, vlan_id_index)

    # Extract container configurations for MikroTik routers
    containers = _extract_containers(container_rows, router_ids)

    capability_flags = _derive_mikrotik_capability_flags(routers)
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
